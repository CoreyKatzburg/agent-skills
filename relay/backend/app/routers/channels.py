"""The browser API for channels: membership, messages, threads, and live updates.

Anyone with a channel's link can read it. Posting needs a joined user (X-User-Id header).
"""

import asyncio
import contextlib
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_session
from app.errors import ApiError, ErrorCode
from app.models import Channel, Participant, ParticipantStatus
from app.realtime import hub
from app.routers.users import CurrentUser
from app.schemas import (
    ChannelCreate,
    ChannelOut,
    ChannelUpdate,
    FollowUpdate,
    MessageCreate,
    MessageOut,
    MessagePage,
    ParticipantOut,
    ParticipantsResponse,
    ThreadOut,
    ThreadSubscriptionOut,
)
from app.services import channels, messages, participants

router = APIRouter(prefix="/v1/channels", tags=["browser"])

DatabaseSession = Annotated[Session, Depends(get_session)]
OptionalUserId = Annotated[str | None, Header(alias="X-User-Id")]


def existing_channel(channel_id: str, session: DatabaseSession) -> Channel:
    return participants.find_channel(session, channel_id)


ExistingChannel = Annotated[Channel, Depends(existing_channel)]


def require_member(session: Session, channel: Channel, user_id: str) -> Participant:
    member = participants.find_active_person(session, channel.id, user_id)
    if member is None:
        raise ApiError(ErrorCode.PERMISSION_DENIED, "Join the channel first.")
    return member


@router.post("", response_model=ChannelOut, status_code=201)
def create_channel(body: ChannelCreate, user: CurrentUser, session: DatabaseSession) -> ChannelOut:
    channel = channels.create_channel(session, user, body.name)
    return channels.present_channel(session, channel, user.id)


@router.get("/{channel_id}", response_model=ChannelOut)
def get_channel(
    channel: ExistingChannel, session: DatabaseSession, user_id: OptionalUserId = None
) -> ChannelOut:
    return channels.present_channel(session, channel, user_id)


@router.patch("/{channel_id}", response_model=ChannelOut)
def rename_channel(
    body: ChannelUpdate, channel: ExistingChannel, user: CurrentUser, session: DatabaseSession
) -> ChannelOut:
    channels.rename_channel(session, channel, user, body.name)
    return channels.present_channel(session, channel, user.id)


@router.delete("/{channel_id}", status_code=204)
def delete_channel(channel: ExistingChannel, user: CurrentUser, session: DatabaseSession) -> Response:
    channels.delete_channel(session, channel, user)
    return Response(status_code=204)


@router.post("/{channel_id}/join", response_model=ParticipantOut)
def join_channel(channel: ExistingChannel, user: CurrentUser, session: DatabaseSession) -> ParticipantOut:
    return participants.present_participant(participants.join_as_person(session, channel, user))


@router.post("/{channel_id}/leave", status_code=204)
def leave_channel(channel: ExistingChannel, user: CurrentUser, session: DatabaseSession) -> Response:
    if channel.owner_user_id == user.id:
        raise ApiError(ErrorCode.INVALID_ARGUMENT, "Owners delete their channel instead of leaving.")
    participants.leave_channel(session, require_member(session, channel, user.id))
    return Response(status_code=204)


@router.get("/{channel_id}/participants", response_model=ParticipantsResponse, tags=["agent"])
def list_participants(channel: ExistingChannel, session: DatabaseSession) -> ParticipantsResponse:
    """List the channel's current participants. Use their ids to mention them."""
    return ParticipantsResponse(
        participants=participants.list_active_participants(session, channel.id)
    )


@router.delete("/{channel_id}/participants/{participant_id}", status_code=204)
def remove_participant(
    participant_id: str, channel: ExistingChannel, user: CurrentUser, session: DatabaseSession
) -> Response:
    channels.require_owner(channel, user)
    target = session.get(Participant, participant_id)
    if target is None or target.channel_id != channel.id or target.status != ParticipantStatus.ACTIVE:
        raise ApiError(ErrorCode.NOT_FOUND, "That participant is not in this channel.")
    if target.user_id == user.id:
        raise ApiError(ErrorCode.INVALID_ARGUMENT, "You cannot remove yourself.")
    participants.remove_participant(session, target)
    return Response(status_code=204)


@router.get("/{channel_id}/messages", response_model=MessagePage)
def list_messages(
    channel: ExistingChannel, session: DatabaseSession, before: int | None = None
) -> MessagePage:
    """Root messages, newest page first. Pass the oldest seq you have as `before` for older ones."""
    return messages.list_root_messages(session, channel.id, before_seq=before)


@router.post("/{channel_id}/messages", response_model=MessageOut)
def send_message(
    body: MessageCreate, channel: ExistingChannel, user: CurrentUser, session: DatabaseSession
) -> MessageOut:
    sent = messages.send_message(
        session,
        channel,
        require_member(session, channel, user.id),
        body=body.body,
        request_id=body.request_id,
        thread_id=body.thread_id,
        reply_to_message_id=body.reply_to_message_id,
    )
    return messages.present_messages(session, [sent])[0]


@router.delete("/{channel_id}/messages/{message_id}", status_code=204)
def delete_message(
    message_id: str, channel: ExistingChannel, user: CurrentUser, session: DatabaseSession
) -> Response:
    messages.delete_message(session, channel, require_member(session, channel, user.id), message_id)
    return Response(status_code=204)


@router.get("/{channel_id}/threads/{thread_id}", response_model=ThreadOut)
def get_thread(
    thread_id: str,
    channel: ExistingChannel,
    session: DatabaseSession,
    user_id: OptionalUserId = None,
) -> ThreadOut:
    viewer = participants.find_active_person(session, channel.id, user_id) if user_id else None
    return messages.get_thread(session, channel.id, thread_id, viewer)


@router.put("/{channel_id}/threads/{thread_id}/follow", response_model=ThreadSubscriptionOut)
def follow_thread(
    thread_id: str,
    body: FollowUpdate,
    channel: ExistingChannel,
    user: CurrentUser,
    session: DatabaseSession,
) -> ThreadSubscriptionOut:
    member = require_member(session, channel, user.id)
    root_id = messages.set_following(session, channel, member, thread_id, body.following)
    return ThreadSubscriptionOut(thread_id=root_id, following=body.following)


@router.websocket("/{channel_id}/live")
async def live_updates(websocket: WebSocket, channel_id: str) -> None:
    """Pushes {"type": ...} events while a channel is open in the browser.

    The browser first sends {"userId": "..."} (or {} when it has no account), so the user
    id never appears in a URL or a server log. Event types:
      "message"        a message was created or changed; the event carries it
      "participants"   someone joined, left, renamed, or came online
      "channel"        the channel was renamed
      "channelDeleted" the channel is gone
    """
    await websocket.accept()
    try:
        hello = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        participant_id = await run_in_threadpool(_member_id, channel_id, hello.get("userId"))
    except (TimeoutError, WebSocketDisconnect, ValueError, AttributeError, ApiError):
        await websocket.close()
        return

    queue = hub.connect_browser(channel_id, participant_id)
    if participant_id:
        hub.publish(channel_id, {"type": "participants"})
    forwarder = asyncio.create_task(_forward_events(queue, websocket))
    try:
        while True:
            # The browser sends nothing else; this just notices when it disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        forwarder.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await forwarder
        hub.disconnect_browser(channel_id, participant_id, queue)
        if participant_id:
            hub.publish(channel_id, {"type": "participants"})


def _member_id(channel_id: str, user_id: str | None) -> str | None:
    with SessionLocal() as session:
        participants.find_channel(session, channel_id)
        member = participants.find_active_person(session, channel_id, user_id) if user_id else None
        return member.id if member else None


async def _forward_events(queue: asyncio.Queue, websocket: WebSocket) -> None:
    while True:
        await websocket.send_json(await queue.get())
