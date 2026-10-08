"""Sending, deleting, listing, and presenting messages, plus following threads."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import MAX_MENTIONED_PARTICIPANTS, MAX_MESSAGE_LENGTH, MESSAGE_PAGE_SIZE
from app.errors import ApiError, ErrorCode
from app.ids import new_message_id
from app.mentions import MentionCandidate, resolve_mentions
from app.models import (
    GENERAL_THREAD_ID,
    Channel,
    Message,
    MessageKind,
    Participant,
    ParticipantStatus,
    ThreadFollow,
)
from app.realtime import hub
from app.schemas import MessageOut, MessagePage, ThreadOut


def send_message(
    session: Session,
    channel: Channel,
    author: Participant,
    body: str,
    request_id: str,
    thread_id: str | None = None,
    reply_to_message_id: str | None = None,
    extra_mention_ids: list[str] | None = None,
) -> Message:
    """Post a root message (thread_id="general") or a reply (any message id in the thread)."""
    already_sent = session.scalar(
        select(Message).where(Message.participant_id == author.id, Message.request_id == request_id)
    )
    if already_sent:
        return already_sent

    target_id = thread_id if reply_to_message_id is None else reply_to_message_id
    if target_id is None or (thread_id is not None and reply_to_message_id is not None):
        raise ApiError(
            ErrorCode.INVALID_ARGUMENT, "Provide exactly one of threadId or replyToMessageId."
        )
    if reply_to_message_id == GENERAL_THREAD_ID:
        raise ApiError(ErrorCode.INVALID_ARGUMENT, "replyToMessageId cannot be 'general'.")
    root = (
        None
        if target_id == GENERAL_THREAD_ID
        else find_thread_root(session, channel.id, target_id)
    )

    body = body.strip()
    if not body:
        raise ApiError(ErrorCode.INVALID_ARGUMENT, "The message is empty.")
    if len(body) > MAX_MESSAGE_LENGTH:
        raise ApiError(
            ErrorCode.LIMIT_EXCEEDED, f"Messages can be at most {MAX_MESSAGE_LENGTH} characters."
        )

    body, mention_ids = _resolve_all_mentions(session, channel.id, body, extra_mention_ids or [])

    message = Message(
        id=new_message_id(),
        channel_id=channel.id,
        parent_thread_id=root.id if root else GENERAL_THREAD_ID,
        participant_id=author.id,
        body=body,
        mention_participant_ids=mention_ids,
        request_id=request_id,
    )
    session.add(message)

    # Posting in a thread, or being mentioned in it, follows that thread.
    root_id = root.id if root else message.id
    for participant_id in dict.fromkeys([author.id, *mention_ids]):
        _follow(session, participant_id, root_id)

    session.commit()
    announce_message(session, message)
    return message


def delete_message(session: Session, channel: Channel, author: Participant, message_id: str) -> None:
    """Replace a message with a tombstone, so replies keep their place under it."""
    message = find_message(session, channel.id, message_id)
    if message.participant_id != author.id or message.kind != MessageKind.MESSAGE:
        raise ApiError(ErrorCode.PERMISSION_DENIED, "You can only delete your own messages.")
    message.deleted = True
    message.body = ""
    message.mention_participant_ids = []
    session.commit()
    announce_message(session, message)


def add_event(session: Session, participant: Participant, sentence: str) -> Message:
    """Record something that happened, e.g. "joined the channel". The caller commits."""
    # Write a just-created participant first, so the event's reference to it is valid.
    session.flush()
    event = Message(
        id=new_message_id(),
        channel_id=participant.channel_id,
        parent_thread_id=GENERAL_THREAD_ID,
        participant_id=participant.id,
        kind=MessageKind.EVENT,
        body=sentence,
    )
    session.add(event)
    return event


def set_following(
    session: Session, channel: Channel, participant: Participant, thread_id: str, following: bool
) -> str:
    """Follow or unfollow a thread. Returns the thread's root id."""
    root = find_thread_root(session, channel.id, thread_id)
    if following:
        _follow(session, participant.id, root.id)
    else:
        existing = session.get(ThreadFollow, (participant.id, root.id))
        if existing:
            session.delete(existing)
    session.commit()
    return root.id


def is_following(session: Session, participant_id: str, thread_id: str) -> bool:
    return session.get(ThreadFollow, (participant_id, thread_id)) is not None


def followed_thread_ids(session: Session, participant_id: str) -> set[str]:
    return set(
        session.scalars(
            select(ThreadFollow.thread_id).where(ThreadFollow.participant_id == participant_id)
        )
    )


def list_root_messages(
    session: Session, channel_id: str, before_seq: int | None = None, limit: int = MESSAGE_PAGE_SIZE
) -> MessagePage:
    """The newest root messages (oldest first), optionally only those older than before_seq."""
    query = select(Message).where(
        Message.channel_id == channel_id, Message.parent_thread_id == GENERAL_THREAD_ID
    )
    if before_seq is not None:
        query = query.where(Message.seq < before_seq)
    newest_first = list(session.scalars(query.order_by(Message.seq.desc()).limit(limit + 1)))
    has_older = len(newest_first) > limit
    page = list(reversed(newest_first[:limit]))
    return MessagePage(messages=present_messages(session, page), has_older=has_older)


def get_thread(
    session: Session, channel_id: str, thread_id: str, viewer: Participant | None
) -> ThreadOut:
    root = find_thread_root(session, channel_id, thread_id)
    replies = list(
        session.scalars(
            select(Message).where(Message.parent_thread_id == root.id).order_by(Message.seq)
        )
    )
    presented = present_messages(session, [root, *replies])
    return ThreadOut(
        root=presented[0],
        replies=presented[1:],
        following=bool(viewer and is_following(session, viewer.id, root.id)),
    )


def find_message(session: Session, channel_id: str, message_id: str) -> Message:
    message = session.scalar(
        select(Message).where(Message.channel_id == channel_id, Message.id == message_id)
    )
    if message is None:
        raise ApiError(ErrorCode.NOT_FOUND, f"Message {message_id} was not found in this channel.")
    return message


def find_thread_root(session: Session, channel_id: str, message_id: str) -> Message:
    """Given any message in a thread (the root or a reply), return the root message."""
    message = find_message(session, channel_id, message_id)
    if message.parent_thread_id != GENERAL_THREAD_ID:
        message = find_message(session, channel_id, message.parent_thread_id)
    if message.kind != MessageKind.MESSAGE:
        raise ApiError(ErrorCode.INVALID_ARGUMENT, "Events cannot have threads.")
    return message


def present_messages(session: Session, messages: list[Message]) -> list[MessageOut]:
    """Turn database rows into API messages, adding sender details and reply summaries."""
    if not messages:
        return []
    root_ids = [m.id for m in messages if m.parent_thread_id == GENERAL_THREAD_ID]
    replies = session.scalars(
        select(Message)
        .where(Message.parent_thread_id.in_(root_ids), Message.deleted.is_(False))
        .order_by(Message.seq)
    )
    replies_by_root: dict[str, list[Message]] = {}
    for reply in replies:
        replies_by_root.setdefault(reply.parent_thread_id, []).append(reply)

    sender_ids = {m.participant_id for m in messages}
    senders = {
        p.id: p for p in session.scalars(select(Participant).where(Participant.id.in_(sender_ids)))
    }

    presented = []
    for message in messages:
        sender = senders[message.participant_id]
        thread_replies = replies_by_root.get(message.id, [])
        presented.append(
            MessageOut(
                thread_id=message.id,
                parent_thread_id=message.parent_thread_id,
                seq=message.seq,
                participant_id=message.participant_id,
                sender_display=sender.display_name,
                sender_kind=sender.kind,
                sender_icon=sender.icon,
                kind=message.kind,
                body=message.body,
                mention_participant_ids=message.mention_participant_ids,
                reply_count=len(thread_replies),
                reply_participant_ids=list(dict.fromkeys(r.participant_id for r in thread_replies)),
                last_reply_at=thread_replies[-1].created_at if thread_replies else None,
                request_id=message.request_id,
                deleted=message.deleted,
                created_at=message.created_at,
            )
        )
    return presented


def announce_message(session: Session, message: Message) -> None:
    """Push a new or changed message to open browsers. A reply also changes its root's summary."""
    changed = [message]
    if message.parent_thread_id != GENERAL_THREAD_ID:
        changed.append(find_message(session, message.channel_id, message.parent_thread_id))
    for presented in present_messages(session, changed):
        hub.publish(
            message.channel_id,
            {"type": "message", "message": presented.model_dump(mode="json", by_alias=True)},
        )


def _resolve_all_mentions(
    session: Session, channel_id: str, body: str, extra_mention_ids: list[str]
) -> tuple[str, list[str]]:
    members = session.scalars(
        select(Participant).where(
            Participant.channel_id == channel_id, Participant.status == ParticipantStatus.ACTIVE
        )
    ).all()
    member_ids = {member.id for member in members}
    unknown_ids = [pid for pid in extra_mention_ids if pid not in member_ids]
    if unknown_ids:
        raise ApiError(
            ErrorCode.INVALID_ARGUMENT, f"Unknown participant ids: {', '.join(unknown_ids)}."
        )

    candidates = [MentionCandidate(member.id, member.display_name) for member in members]
    body, inline_ids = resolve_mentions(body, candidates)
    all_ids = list(dict.fromkeys([*inline_ids, *extra_mention_ids]))
    if len(all_ids) > MAX_MENTIONED_PARTICIPANTS:
        raise ApiError(
            ErrorCode.LIMIT_EXCEEDED,
            f"A message can mention at most {MAX_MENTIONED_PARTICIPANTS} participants.",
        )
    return body, all_ids


def _follow(session: Session, participant_id: str, thread_id: str) -> None:
    if session.get(ThreadFollow, (participant_id, thread_id)) is None:
        session.add(ThreadFollow(participant_id=participant_id, thread_id=thread_id))
