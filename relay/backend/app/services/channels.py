"""Creating, renaming, deleting, and listing channels, and browser user accounts."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import MAX_CHANNEL_NAME_LENGTH, MAX_CHANNELS_PER_USER
from app.errors import ApiError, ErrorCode
from app.ids import new_channel_id, new_secret
from app.models import Channel, Participant, ParticipantStatus, User
from app.realtime import hub
from app.schemas import ChannelOut, ChannelSummary, UserChannelsResponse
from app.services.participants import (
    clean_display_name,
    find_active_person,
    join_as_person,
    present_participant,
)


def create_user(session: Session, display_name: str) -> User:
    user = User(id=new_secret(), display_name=clean_display_name(display_name))
    session.add(user)
    session.commit()
    return user


def find_user(session: Session, user_id: str | None) -> User:
    user = session.get(User, user_id) if user_id else None
    if user is None:
        raise ApiError(ErrorCode.INVALID_IDENTITY, "Unknown user. Pick a name to continue.")
    return user


def clean_channel_name(raw_name: str) -> str:
    name = raw_name.strip().lstrip("#").strip()
    if not 1 <= len(name) <= MAX_CHANNEL_NAME_LENGTH:
        raise ApiError(
            ErrorCode.INVALID_ARGUMENT,
            f"Channel names must be 1 to {MAX_CHANNEL_NAME_LENGTH} characters.",
        )
    return name


def create_channel(session: Session, owner: User, name: str) -> Channel:
    owned_count = (
        session.scalar(
            select(func.count()).select_from(Channel).where(Channel.owner_user_id == owner.id)
        )
        or 0
    )
    if owned_count >= MAX_CHANNELS_PER_USER:
        raise ApiError(
            ErrorCode.LIMIT_EXCEEDED, f"You can own at most {MAX_CHANNELS_PER_USER} channels."
        )
    channel = Channel(id=new_channel_id(), name=clean_channel_name(name), owner_user_id=owner.id)
    session.add(channel)
    session.flush()
    join_as_person(session, channel, owner)
    return channel


def rename_channel(session: Session, channel: Channel, user: User, new_name: str) -> Channel:
    require_owner(channel, user)
    channel.name = clean_channel_name(new_name)
    session.commit()
    hub.publish(channel.id, {"type": "channel"})
    return channel


def delete_channel(session: Session, channel: Channel, user: User) -> None:
    require_owner(channel, user)
    channel_id = channel.id
    session.delete(channel)
    session.commit()
    hub.publish(channel_id, {"type": "channelDeleted"})


def require_owner(channel: Channel, user: User) -> None:
    if channel.owner_user_id != user.id:
        raise ApiError(ErrorCode.PERMISSION_DENIED, "Only the channel's owner can do that.")


def present_channel(session: Session, channel: Channel, user_id: str | None) -> ChannelOut:
    me = find_active_person(session, channel.id, user_id) if user_id else None
    online_people = hub.online_participant_ids(channel.id)
    return ChannelOut(
        id=channel.id,
        name=channel.name,
        created_at=channel.created_at,
        is_owner=channel.owner_user_id == user_id,
        me=present_participant(me, online_people) if me else None,
    )


def list_user_channels(session: Session, user: User) -> UserChannelsResponse:
    """Channels the user owns, and channels others own that the user has joined."""
    joined = session.scalars(
        select(Channel)
        .join(Participant, Participant.channel_id == Channel.id)
        .where(Participant.user_id == user.id, Participant.status == ParticipantStatus.ACTIVE)
        .order_by(Channel.created_at)
    )
    owned, shared = [], []
    for channel in joined:
        summary = ChannelSummary(id=channel.id, name=channel.name)
        (owned if channel.owner_user_id == user.id else shared).append(summary)
    return UserChannelsResponse(owned=owned, shared=shared)
