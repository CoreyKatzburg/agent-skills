"""Database tables."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime, utc_now

# Root messages are posted to this pseudo thread. Replies are posted to their root message's id.
GENERAL_THREAD_ID = "general"


class ParticipantKind(StrEnum):
    PERSON = "person"
    AGENT = "agent"


class ParticipantStatus(StrEnum):
    ACTIVE = "active"
    LEFT = "left"
    REMOVED = "removed"


class MessageKind(StrEnum):
    MESSAGE = "message"
    # Something that happened, like "joined the channel". The body completes "<sender> ...".
    EVENT = "event"


class AgentIcon(StrEnum):
    """The model or provider an agent runs on. Shown beside its messages."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    XAI = "xai"
    DEEPSEEK = "deepseek"
    META = "meta"
    MISTRAL = "mistral"
    QWEN = "qwen"
    COHERE = "cohere"
    PERPLEXITY = "perplexity"
    MICROSOFT = "microsoft"
    AMAZON = "amazon"
    NVIDIA = "nvidia"
    MOONSHOT = "moonshot"
    ZHIPU = "zhipu"
    MINIMAX = "minimax"
    ROBOT = "robot"


class User(Base):
    """A person using the browser app. There is no sign-up: the browser keeps the id."""

    __tablename__ = "users"

    # Secret: whoever holds this id acts as this user, so it never appears in links.
    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str]
    # Activity items newer than this show as unread.
    activity_read_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str]
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class Participant(Base):
    """A person or agent who belongs (or belonged) to one channel."""

    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint("channel_id", "user_id"),
        UniqueConstraint("channel_id", "register_request_id"),
    )

    # Public id used for mentions, e.g. "release-bot-k3j9x0a1b2c3". Never changes.
    id: Mapped[str] = mapped_column(String, primary_key=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    kind: Mapped[ParticipantKind] = mapped_column(String)
    display_name: Mapped[str]
    icon: Mapped[AgentIcon | None] = mapped_column(String, default=None)
    status: Mapped[ParticipantStatus] = mapped_column(String, default=ParticipantStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    # People only: the browser user behind this participant.
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)

    # Agents only: the secret token in their URLs and the request id they registered with.
    # Replaying the registration request id recovers the identity (or rejoins after leaving).
    token: Mapped[str | None] = mapped_column(String, unique=True, default=None)
    register_request_id: Mapped[str | None] = mapped_column(String, default=None)
    last_polled_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    # Agents only: where their activity feed is up to. See services/activity.py.
    activity_cursor_seq: Mapped[int] = mapped_column(default=0)
    pending_batch_id: Mapped[str | None] = mapped_column(String, default=None)
    pending_batch_seqs: Mapped[list[int]] = mapped_column(JSON, default=list)
    pending_batch_remaining_unread: Mapped[int] = mapped_column(default=0)
    last_acknowledged_batch_id: Mapped[str | None] = mapped_column(String, default=None)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("participant_id", "request_id"),)

    # Increases with every message, so it gives a reliable order and a cursor for agents.
    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Public id, e.g. "thread_ab12...". Called "threadId" in the API because a message
    # id is also the id of the thread that hangs off it.
    id: Mapped[str] = mapped_column(String, unique=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    # GENERAL_THREAD_ID for a root message, or the root message's id for a reply.
    parent_thread_id: Mapped[str] = mapped_column(String, index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    kind: Mapped[MessageKind] = mapped_column(String, default=MessageKind.MESSAGE)
    body: Mapped[str]
    mention_participant_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    # The sender's idempotency key, so a retried send does not post twice.
    request_id: Mapped[str | None] = mapped_column(String, default=None)
    deleted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class ThreadFollow(Base):
    """A participant following a thread gets its replies in their activity."""

    __tablename__ = "thread_follows"

    participant_id: Mapped[str] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True
    )
    thread_id: Mapped[str] = mapped_column(String, primary_key=True)
