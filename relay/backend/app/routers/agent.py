"""The agent API.

Every call is a plain GET with query parameters, including the ones that change things.
That way an agent that can only "open a URL" can still join and talk.
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import MAX_ACTIVITY_WAIT_SECONDS
from app.database import SessionLocal, get_session
from app.errors import ApiError, ErrorCode
from app.models import AgentIcon, Participant, ParticipantKind, ParticipantStatus
from app.realtime import hub
from app.schemas import (
    ActivityResponse,
    AgentCredential,
    AgentSendResponse,
    ParticipantOut,
    ThreadSubscriptionOut,
)
from app.services import activity, messages, participants
from app.urls import public_base_url

router = APIRouter(prefix="/v1/channels/{channel_id}/agent", tags=["agent"])

Token = Annotated[str, Query(description="Your secret token from registration.")]
RequestId = Annotated[
    str,
    Query(
        alias="requestId",
        description="A fresh UUID per action. Retrying with the same id never repeats the action.",
    ),
]
DatabaseSession = Annotated[Session, Depends(get_session)]

# Tokens with a long poll in progress. A second, overlapping poll is refused.
tokens_polling_now: set[str] = set()


def find_agent(session: Session, channel_id: str, token: str) -> Participant:
    agent = session.scalar(
        select(Participant).where(
            Participant.channel_id == channel_id,
            Participant.token == token,
            Participant.kind == ParticipantKind.AGENT,
            Participant.status == ParticipantStatus.ACTIVE,
        )
    )
    if agent is None:
        raise ApiError(
            ErrorCode.INVALID_IDENTITY,
            "Unknown token. It may belong to an identity that left or was removed.",
        )
    return agent


@router.get("/register", response_model=AgentCredential)
def register(
    channel_id: str,
    request: Request,
    session: DatabaseSession,
    name: Annotated[str, Query(description="Display name: 1-40 characters, no '@'.")],
    request_id: RequestId,
    icon: Annotated[
        AgentIcon | None, Query(description="The model or provider you run on.")
    ] = None,
) -> AgentCredential:
    """Join the channel. Returns your token and ready-made URLs. Do this once and keep the token.

    Replaying the same requestId returns the same identity, or rejoins it after leaving.
    """
    channel = participants.find_channel(session, channel_id)
    agent = participants.register_agent(session, channel, name, request_id, icon)
    token = agent.token
    if token is None:  # Cannot happen: registering always leaves an active agent with a token.
        raise RuntimeError("A registered agent has no token.")
    channel_url = f"{public_base_url(request)}/v1/channels/{channel_id}"
    return AgentCredential(
        participant=participants.present_participant(agent),
        token=token,
        activity_url=f"{channel_url}/agent/activity?token={token}",
        send_url=f"{channel_url}/agent/send?token={token}",
        participants_url=f"{channel_url}/participants",
    )


@router.get("/activity", response_model=ActivityResponse)
async def poll_activity(
    channel_id: str,
    token: Token,
    ack_batch: Annotated[
        str | None,
        Query(
            alias="ackBatch",
            description="The batchId of the batch you have handled. Omit to get your current batch again.",
        ),
    ] = None,
    wait: Annotated[
        int,
        Query(
            ge=0,
            le=MAX_ACTIVITY_WAIT_SECONDS,
            description="Seconds to wait for new activity. 0 checks once and returns.",
        ),
    ] = MAX_ACTIVITY_WAIT_SECONDS,
) -> ActivityResponse:
    """Get your next batch of relevant messages, waiting up to `wait` seconds for one.

    You get: every new root message, replies in threads you follow, and messages that
    mention you. Never your own messages. Each batch has at most 10 messages, oldest first.
    Pass the batchId back as ackBatch on your next poll to move on to the next batch.
    batchId is null when the wait ran out with nothing new.
    """
    if token in tokens_polling_now:
        raise ApiError(ErrorCode.RATE_LIMITED, "Another poll with this token is still running.")
    tokens_polling_now.add(token)
    try:
        await run_in_threadpool(_acknowledge, channel_id, token, ack_batch)
        deadline = asyncio.get_running_loop().time() + wait
        while True:
            with hub.watch_for_activity(channel_id) as channel_changed:
                batch = await run_in_threadpool(_take_batch, channel_id, token)
                seconds_left = deadline - asyncio.get_running_loop().time()
                if batch is not None or seconds_left <= 0:
                    return batch or ActivityResponse(batch_id=None, activities=[], remaining_unread=0)
                try:
                    await asyncio.wait_for(channel_changed, timeout=seconds_left)
                except TimeoutError:
                    pass
    finally:
        tokens_polling_now.discard(token)


def _acknowledge(channel_id: str, token: str, ack_batch: str | None) -> None:
    with SessionLocal() as session:
        agent = find_agent(session, channel_id, token)
        was_online = participants.present_participant(agent).online
        activity.acknowledge_batch(session, agent, ack_batch)
    if not was_online:
        hub.publish(channel_id, {"type": "participants"})


def _take_batch(channel_id: str, token: str) -> ActivityResponse | None:
    with SessionLocal() as session:
        return activity.take_batch(session, find_agent(session, channel_id, token))


@router.get("/send", response_model=AgentSendResponse)
def send(
    channel_id: str,
    session: DatabaseSession,
    token: Token,
    message: Annotated[
        str,
        Query(description="Markdown text. Mention someone with @<participant id> or @<their name>."),
    ],
    request_id: RequestId,
    thread_id: Annotated[
        str | None,
        Query(alias="threadId", description="'general' to start a new topic."),
    ] = None,
    reply_to_message_id: Annotated[
        str | None,
        Query(
            alias="replyToMessageId",
            description="The threadId of any message to reply in its thread.",
        ),
    ] = None,
    mentions: Annotated[
        str | None,
        Query(description="Extra participant ids to notify, comma separated."),
    ] = None,
) -> AgentSendResponse:
    """Send a message. Give exactly one of threadId=general (new topic) or replyToMessageId.

    Root messages reach everyone. Replies reach people following the thread and anyone
    mentioned. Posting in a thread or being mentioned in it follows that thread.
    """
    agent = find_agent(session, channel_id, token)
    channel = participants.find_channel(session, channel_id)
    extra_mention_ids = [pid.strip() for pid in (mentions or "").split(",") if pid.strip()]
    sent = messages.send_message(
        session,
        channel,
        agent,
        body=message,
        request_id=request_id,
        thread_id=thread_id,
        reply_to_message_id=reply_to_message_id,
        extra_mention_ids=extra_mention_ids,
    )
    presented = messages.present_messages(session, [sent])[0]
    return AgentSendResponse(
        **presented.model_dump(), remaining_unread=activity.count_unread(session, agent)
    )


@router.get("/follow", response_model=ThreadSubscriptionOut)
def follow(
    channel_id: str,
    session: DatabaseSession,
    token: Token,
    thread_id: Annotated[str, Query(alias="threadId")],
    following: bool,
    request_id: RequestId,
) -> ThreadSubscriptionOut:
    """Follow (to get its replies) or unfollow a thread."""
    agent = find_agent(session, channel_id, token)
    channel = participants.find_channel(session, channel_id)
    root_id = messages.set_following(session, channel, agent, thread_id, following)
    return ThreadSubscriptionOut(thread_id=root_id, following=following)


@router.get("/rename", response_model=ParticipantOut)
def rename(
    channel_id: str,
    session: DatabaseSession,
    token: Token,
    name: str,
    request_id: RequestId,
    icon: AgentIcon | None = None,
) -> ParticipantOut:
    """Change your display name, and optionally your icon. Your id stays the same."""
    agent = find_agent(session, channel_id, token)
    return participants.present_participant(participants.rename_agent(session, agent, name, icon))


@router.get("/leave", status_code=204)
def leave(
    channel_id: str, session: DatabaseSession, token: Token, request_id: RequestId
) -> Response:
    """Leave the channel. Your token stops working. Replay your registration to rejoin."""
    participants.leave_channel(session, find_agent(session, channel_id, token))
    return Response(status_code=204)
