// Shapes returned by the backend. They mirror backend/app/schemas.py.

export const GENERAL_THREAD_ID = "general";

export type AgentIcon =
  | "openai"
  | "anthropic"
  | "google"
  | "xai"
  | "deepseek"
  | "meta"
  | "mistral"
  | "qwen"
  | "cohere"
  | "perplexity"
  | "microsoft"
  | "amazon"
  | "nvidia"
  | "moonshot"
  | "zhipu"
  | "minimax"
  | "robot";

export type ParticipantKind = "person" | "agent";

export interface Participant {
  id: string;
  displayName: string;
  kind: ParticipantKind;
  icon: AgentIcon | null;
  active: boolean;
  online: boolean;
  createdAt: string;
}

export interface Message {
  /** The message's own id. Also the id of the thread of replies under it. */
  threadId: string;
  /** "general" for a root message, or the root message's id for a reply. */
  parentThreadId: string;
  seq: number;
  participantId: string;
  senderDisplay: string;
  senderKind: ParticipantKind;
  senderIcon: AgentIcon | null;
  /** "event" is something that happened, like "joined the channel". */
  kind: "message" | "event";
  /** Markdown. Mentions appear as "@<participant id>". */
  body: string;
  mentionParticipantIds: string[];
  /** Current display name of each mentioned participant, by id. */
  mentionNames: Record<string, string>;
  replyCount: number;
  replyParticipantIds: string[];
  lastReplyAt: string | null;
  requestId: string | null;
  deleted: boolean;
  createdAt: string;
}

export interface User {
  id: string;
  displayName: string;
}

export interface ChannelSummary {
  id: string;
  name: string;
}

export interface UserChannels {
  owned: ChannelSummary[];
  shared: ChannelSummary[];
}

export interface Channel {
  id: string;
  name: string;
  createdAt: string;
  isOwner: boolean;
  /** Your membership, or null if you have not joined. */
  me: Participant | null;
}

export interface MessagePage {
  messages: Message[];
  hasOlder: boolean;
}

export interface Thread {
  root: Message;
  replies: Message[];
  following: boolean;
}

export interface PersonActivityItem {
  channelId: string;
  channelName: string;
  message: Message;
  reasons: string[];
  unread: boolean;
}

export interface PersonActivity {
  items: PersonActivityItem[];
  unreadCount: number;
}

/** Events pushed over the channel's live-update WebSocket. */
export type LiveEvent =
  | { type: "message"; message: Message }
  | { type: "participants" }
  | { type: "channel" }
  | { type: "channelDeleted" };
