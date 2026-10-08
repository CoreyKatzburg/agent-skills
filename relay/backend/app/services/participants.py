"""Joining, registering, renaming, leaving, and removing participants."""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import (
    AGENT_ONLINE_WINDOW_SECONDS,
    MAX_DISPLAY_NAME_LENGTH,
    MAX_PARTICIPANTS_PER_CHANNEL,
)
from app.database import utc_now
from app.errors import ApiError, ErrorCode
from app.ids import new_participant_id, new_secret
from app.models import (
    AgentIcon,
    Channel,
    Message,
    Participant,
    ParticipantKind,
    ParticipantStatus,
    User,
)
from app.realtime import hub
from app.schemas import ParticipantOut
from app.services.messages import add_event, announce_message


def clean_display_name(raw_name: str) -> str:
    name = raw_name.strip()
    if not 1 <= len(name) <= MAX_DISPLAY_NAME_LENGTH:
        raise ApiError(
            ErrorCode.INVALID_ARGUMENT,
            f"Names must be 1 to {MAX_DISPLAY_NAME_LENGTH} characters.",
        )
    if "@" in name:
        raise ApiError(ErrorCode.INVALID_ARGUMENT, "Names cannot contain '@'.")
    return name


def find_channel(session: Session, channel_id: str) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise ApiError(ErrorCode.NOT_FOUND, "This channel does not exist. It may have been deleted.")
    return channel


def find_person(session: Session, channel_id: str, user_id: str) -> Participant | None:
    return session.scalar(
        select(Participant).where(
            Participant.channel_id == channel_id, Participant.user_id == user_id
        )
    )


def find_active_person(session: Session, channel_id: str, user_id: str) -> Participant | None:
    person = find_person(session, channel_id, user_id)
    return person if person and person.status == ParticipantStatus.ACTIVE else None


def list_active_participants(session: Session, channel_id: str) -> list[ParticipantOut]:
    members = session.scalars(
        select(Participant)
        .where(Participant.channel_id == channel_id, Participant.status == ParticipantStatus.ACTIVE)
        .order_by(Participant.created_at)
    )
    online_people = hub.online_participant_ids(channel_id)
    return [present_participant(member, online_people) for member in members]


def present_participant(
    participant: Participant, online_people: set[str] | None = None
) -> ParticipantOut:
    if participant.kind == ParticipantKind.AGENT:
        recently = utc_now() - timedelta(seconds=AGENT_ONLINE_WINDOW_SECONDS)
        online = participant.last_polled_at is not None and participant.last_polled_at > recently
    else:
        online = participant.id in (online_people or set())
    return ParticipantOut(
        id=participant.id,
        display_name=participant.display_name,
        kind=participant.kind,
        icon=participant.icon,
        active=participant.status == ParticipantStatus.ACTIVE,
        online=online,
        created_at=participant.created_at,
    )


def join_as_person(session: Session, channel: Channel, user: User) -> Participant:
    """Join the channel, or rejoin after leaving or being removed."""
    person = find_person(session, channel.id, user.id)
    if person and person.status == ParticipantStatus.ACTIVE:
        return person

    _ensure_room_for_one_more(session, channel.id)
    if person is None:
        person = Participant(
            id=new_participant_id(user.display_name),
            channel_id=channel.id,
            kind=ParticipantKind.PERSON,
            display_name=user.display_name,
            user_id=user.id,
        )
        session.add(person)
    else:
        person.status = ParticipantStatus.ACTIVE
        person.display_name = user.display_name
    _commit_with_event(session, person, "joined the channel")
    return person


def register_agent(
    session: Session, channel: Channel, name: str, request_id: str, icon: AgentIcon | None
) -> Participant:
    """Create an agent identity. Replaying the same request id returns the same identity."""
    name = clean_display_name(name)
    agent = session.scalar(
        select(Participant).where(
            Participant.channel_id == channel.id, Participant.register_request_id == request_id
        )
    )
    if agent and agent.status == ParticipantStatus.ACTIVE:
        return agent
    if agent and agent.status == ParticipantStatus.REMOVED:
        raise ApiError(ErrorCode.PERMISSION_DENIED, "This identity was removed from the channel.")

    _ensure_room_for_one_more(session, channel.id)
    if agent is None:
        agent = Participant(
            id=new_participant_id(name),
            channel_id=channel.id,
            kind=ParticipantKind.AGENT,
            display_name=name,
            icon=icon,
            register_request_id=request_id,
        )
        session.add(agent)
    else:
        # Rejoining after leaving. Leaving threw the old token away, so issue a new one.
        agent.status = ParticipantStatus.ACTIVE

    agent.token = new_secret()
    # Start the agent's activity feed from now, not from the start of the channel's history.
    agent.activity_cursor_seq = session.scalar(select(func.max(Message.seq))) or 0
    agent.pending_batch_id = None
    agent.pending_batch_seqs = []
    agent.last_acknowledged_batch_id = None
    _commit_with_event(session, agent, "joined the channel")
    return agent


def rename_agent(
    session: Session, agent: Participant, new_name: str, new_icon: AgentIcon | None
) -> Participant:
    new_name = clean_display_name(new_name)
    changes = []
    if new_name != agent.display_name:
        agent.display_name = new_name
        changes.append(f"changed their name to {new_name}")
    if new_icon and new_icon != agent.icon:
        agent.icon = new_icon
        changes.append("changed their icon")
    if changes:
        _commit_with_event(session, agent, " and ".join(changes))
    return agent


def rename_user(session: Session, user: User, new_name: str) -> User:
    """A person's name is shared by every channel they are in."""
    new_name = clean_display_name(new_name)
    if new_name == user.display_name:
        return user
    user.display_name = new_name
    memberships = session.scalars(select(Participant).where(Participant.user_id == user.id)).all()
    events = []
    for person in memberships:
        person.display_name = new_name
        if person.status == ParticipantStatus.ACTIVE:
            events.append(add_event(session, person, f"changed their name to {new_name}"))
    session.commit()
    for event in events:
        announce_message(session, event)
        _announce_participants_changed(event.channel_id)
    return user


def leave_channel(session: Session, participant: Participant) -> None:
    if participant.status != ParticipantStatus.ACTIVE:
        return
    participant.status = ParticipantStatus.LEFT
    participant.token = None
    _commit_with_event(session, participant, "left the channel")


def remove_participant(session: Session, participant: Participant) -> None:
    """Owner-only: take someone out of the channel. Their messages stay."""
    if participant.status != ParticipantStatus.ACTIVE:
        return
    participant.status = ParticipantStatus.REMOVED
    participant.token = None
    _commit_with_event(session, participant, "was removed from the channel")


def _ensure_room_for_one_more(session: Session, channel_id: str) -> None:
    member_count = (
        session.scalar(
            select(func.count()).where(
                Participant.channel_id == channel_id,
                Participant.status == ParticipantStatus.ACTIVE,
            )
        )
        or 0
    )
    if member_count >= MAX_PARTICIPANTS_PER_CHANNEL:
        raise ApiError(
            ErrorCode.LIMIT_EXCEEDED,
            f"A channel can have at most {MAX_PARTICIPANTS_PER_CHANNEL} participants.",
        )


def _commit_with_event(session: Session, participant: Participant, sentence: str) -> None:
    event = add_event(session, participant, sentence)
    session.commit()
    announce_message(session, event)
    _announce_participants_changed(participant.channel_id)


def _announce_participants_changed(channel_id: str) -> None:
    hub.publish(channel_id, {"type": "participants"})
