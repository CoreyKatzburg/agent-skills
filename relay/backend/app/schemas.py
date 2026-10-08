"""Shapes of API requests and responses. Field names are camelCase in JSON."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models import AgentIcon, MessageKind, ParticipantKind


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---- Shared ----


class ParticipantOut(ApiModel):
    id: str = Field(description="Stable id used for mentions. Never changes, even after a rename.")
    display_name: str
    kind: ParticipantKind
    icon: AgentIcon | None = Field(default=None, description="Agents only.")
    active: bool = Field(description="Still a member of the channel.")
    online: bool = Field(description="Has the channel open right now (people) or polled recently (agents).")
    created_at: datetime


class ParticipantsResponse(ApiModel):
    participants: list[ParticipantOut]


class MessageOut(ApiModel):
    thread_id: str = Field(
        description="This message's own id. Pass it as replyToMessageId to reply in its thread."
    )
    parent_thread_id: str = Field(
        description="'general' for a root message, or the root message's id for a reply."
    )
    seq: int
    participant_id: str
    sender_display: str
    sender_kind: ParticipantKind
    sender_icon: AgentIcon | None = None
    kind: MessageKind
    body: str = Field(description="Markdown. Mentions appear as @<participant id>.")
    mention_participant_ids: list[str]
    mention_names: dict[str, str] = Field(
        description="Current display name of each mentioned participant, by id."
    )
    reply_count: int
    reply_participant_ids: list[str] = Field(description="Who has replied. Empty on a reply.")
    last_reply_at: datetime | None = None
    request_id: str | None = None
    deleted: bool
    created_at: datetime


class ThreadSubscriptionOut(ApiModel):
    thread_id: str
    following: bool


# ---- Agent API ----


class AgentCredential(ApiModel):
    participant: ParticipantOut
    token: str
    activity_url: str
    send_url: str
    participants_url: str


class AgentSendResponse(MessageOut):
    remaining_unread: int = Field(description="Relevant messages you have not received yet.")


class ActivityOut(ApiModel):
    message: MessageOut
    reasons: list[str] = Field(description="Why you got it: general, following, and/or mention.")
    following_thread: bool


class ActivityResponse(ApiModel):
    batch_id: str | None = Field(
        description="Pass back as ackBatch on your next poll. Null when the wait timed out."
    )
    activities: list[ActivityOut]
    remaining_unread: int


# ---- Browser API ----


class UserCreate(ApiModel):
    display_name: str


class UserUpdate(ApiModel):
    display_name: str


class UserOut(ApiModel):
    id: str
    display_name: str


class ChannelCreate(ApiModel):
    name: str


class ChannelUpdate(ApiModel):
    name: str


class ChannelSummary(ApiModel):
    id: str
    name: str


class UserChannelsResponse(ApiModel):
    owned: list[ChannelSummary]
    shared: list[ChannelSummary]


class ChannelOut(ApiModel):
    id: str
    name: str
    created_at: datetime
    is_owner: bool
    me: ParticipantOut | None = Field(description="Your membership, if you have joined.")


class MessageCreate(ApiModel):
    body: str
    request_id: str
    thread_id: str | None = None
    reply_to_message_id: str | None = None


class MessagePage(ApiModel):
    messages: list[MessageOut] = Field(description="Oldest first.")
    has_older: bool


class ThreadOut(ApiModel):
    root: MessageOut
    replies: list[MessageOut]
    following: bool


class FollowUpdate(ApiModel):
    following: bool


class PersonActivityItem(ApiModel):
    channel_id: str
    channel_name: str
    message: MessageOut
    reasons: list[str]
    unread: bool


class PersonActivityResponse(ApiModel):
    items: list[PersonActivityItem]
    unread_count: int
