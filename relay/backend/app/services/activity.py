"""Activity: which messages a participant should hear about.

Agents read activity in batches through a long poll. The delivery rules:

1. Each poll returns a batch of up to ACTIVITY_BATCH_SIZE relevant messages, oldest first,
   with a batch id. The batch stays "pending" until the agent acknowledges it.
2. Polling without acknowledging returns the same pending batch again. So if a response
   gets lost on the way, the agent simply polls again and nothing is skipped.
3. Polling with ackBatch=<pending batch id> confirms it and moves on to the next batch.
   Repeating the most recent acknowledgment is harmless. Any other id is rejected.

People see a simpler activity feed in the browser: mentions and replies in threads they follow.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ACTIVITY_BATCH_SIZE, PERSON_ACTIVITY_FEED_SIZE
from app.database import utc_now
from app.errors import ApiError, ErrorCode
from app.ids import new_batch_id
from app.models import (
    GENERAL_THREAD_ID,
    Channel,
    Message,
    MessageKind,
    Participant,
    ParticipantKind,
    ParticipantStatus,
    User,
)
from app.schemas import (
    ActivityOut,
    ActivityResponse,
    PersonActivityItem,
    PersonActivityResponse,
)
from app.services.messages import followed_thread_ids, present_messages


@dataclass(frozen=True)
class RelevantMessage:
    message: Message
    reasons: list[str]


def relevance_reasons(message: Message, participant_id: str, followed: set[str]) -> list[str]:
    """Why a participant should hear about a message. Empty means they should not."""
    if message.kind != MessageKind.MESSAGE or message.deleted:
        return []
    if message.participant_id == participant_id:
        return []
    reasons = []
    if message.parent_thread_id == GENERAL_THREAD_ID:
        reasons.append("general")
    elif message.parent_thread_id in followed:
        reasons.append("following")
    if participant_id in message.mention_participant_ids:
        reasons.append("mention")
    return reasons


# ---- Agents ----


def acknowledge_batch(session: Session, agent: Participant, ack_batch_id: str | None) -> None:
    """Apply an agent's acknowledgment and record that it polled (which shows it as online)."""
    agent.last_polled_at = utc_now()
    if ack_batch_id is not None:
        if ack_batch_id == agent.pending_batch_id:
            agent.last_acknowledged_batch_id = ack_batch_id
            agent.pending_batch_id = None
            agent.pending_batch_seqs = []
            agent.pending_batch_remaining_unread = 0
        elif ack_batch_id != agent.last_acknowledged_batch_id:
            session.rollback()
            raise ApiError(
                ErrorCode.INVALID_ARGUMENT,
                "Unknown or outdated ackBatch. Omit it to get your current batch again.",
                status_code=409,
            )
    session.commit()


def take_batch(session: Session, agent: Participant) -> ActivityResponse | None:
    """Return the pending batch, or start a new one. None when there is nothing to deliver."""
    if agent.pending_batch_id is None:
        unread, newest_checked_seq = _scan_unread(session, agent)
        batch, later = unread[:ACTIVITY_BATCH_SIZE], unread[ACTIVITY_BATCH_SIZE:]
        # Move the cursor past every message checked, relevant or not. Otherwise a reply
        # sent before the agent followed a thread would show up later as if it were new.
        agent.activity_cursor_seq = batch[-1].message.seq if later else newest_checked_seq
        if not batch:
            session.commit()
            return None
        agent.pending_batch_id = new_batch_id()
        agent.pending_batch_seqs = [item.message.seq for item in batch]
        agent.pending_batch_remaining_unread = len(later)
        session.commit()

    # Load the batch fresh each time. Messages deleted since the batch was made drop out,
    # so a batch can come back with no activities; the agent still acknowledges it.
    followed = followed_thread_ids(session, agent.id)
    messages = session.scalars(
        select(Message).where(Message.seq.in_(agent.pending_batch_seqs)).order_by(Message.seq)
    ).all()
    still_relevant = [
        RelevantMessage(message, reasons)
        for message in messages
        if (reasons := relevance_reasons(message, agent.id, followed))
    ]
    return ActivityResponse(
        batch_id=agent.pending_batch_id,
        activities=_present_activities(session, still_relevant, followed),
        remaining_unread=agent.pending_batch_remaining_unread,
    )


def count_unread(session: Session, agent: Participant) -> int:
    """Relevant messages the agent has not been handed yet."""
    unread, _newest_checked_seq = _scan_unread(session, agent)
    return len(unread)


def _scan_unread(session: Session, agent: Participant) -> tuple[list[RelevantMessage], int]:
    """Relevant messages after the agent's cursor, and the newest seq that was checked."""
    followed = followed_thread_ids(session, agent.id)
    newer_messages = session.scalars(
        select(Message)
        .where(Message.channel_id == agent.channel_id, Message.seq > agent.activity_cursor_seq)
        .order_by(Message.seq)
    ).all()
    relevant = [
        RelevantMessage(message, reasons)
        for message in newer_messages
        if (reasons := relevance_reasons(message, agent.id, followed))
    ]
    newest_checked_seq = newer_messages[-1].seq if newer_messages else agent.activity_cursor_seq
    return relevant, newest_checked_seq


def _present_activities(
    session: Session, items: list[RelevantMessage], followed: set[str]
) -> list[ActivityOut]:
    presented = present_messages(session, [item.message for item in items])
    activities = []
    for item, message_out in zip(items, presented, strict=True):
        root_id = (
            item.message.id
            if item.message.parent_thread_id == GENERAL_THREAD_ID
            else item.message.parent_thread_id
        )
        activities.append(
            ActivityOut(message=message_out, reasons=item.reasons, following_thread=root_id in followed)
        )
    return activities


# ---- People ----


def person_activity_feed(session: Session, user: User) -> PersonActivityResponse:
    """Recent mentions of the user, and replies in threads they follow, across their channels."""
    memberships = session.execute(
        select(Participant, Channel)
        .join(Channel, Channel.id == Participant.channel_id)
        .where(
            Participant.user_id == user.id,
            Participant.kind == ParticipantKind.PERSON,
            Participant.status == ParticipantStatus.ACTIVE,
        )
    ).tuples()

    found: list[tuple[Channel, RelevantMessage]] = []
    for person, channel in memberships:
        followed = followed_thread_ids(session, person.id)
        # Only replies and mentions count, so scanning the recent history is enough.
        recent_messages = session.scalars(
            select(Message)
            .where(Message.channel_id == person.channel_id)
            .order_by(Message.seq.desc())
            .limit(PERSON_ACTIVITY_FEED_SIZE * 10)
        )
        for message in recent_messages:
            reasons = [
                reason
                for reason in relevance_reasons(message, person.id, followed)
                if reason != "general"
            ]
            if reasons:
                found.append((channel, RelevantMessage(message, reasons)))

    found.sort(key=lambda channel_and_item: channel_and_item[1].message.seq, reverse=True)
    found = found[:PERSON_ACTIVITY_FEED_SIZE]
    presented = present_messages(session, [item.message for _channel, item in found])
    items = [
        PersonActivityItem(
            channel_id=channel.id,
            channel_name=channel.name,
            message=message_out,
            reasons=item.reasons,
            unread=item.message.created_at > user.activity_read_at,
        )
        for (channel, item), message_out in zip(found, presented, strict=True)
    ]
    return PersonActivityResponse(items=items, unread_count=sum(item.unread for item in items))


def mark_person_activity_read(session: Session, user: User) -> None:
    user.activity_read_at = utc_now()
    session.commit()
