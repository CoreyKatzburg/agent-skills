import type {
  Channel,
  Message,
  MessagePage,
  Participant,
  PersonActivity,
  Thread,
  User,
  UserChannels,
} from "./types";

const USER_ID_STORAGE_KEY = "relay.userId";

/** The browser keeps the user id. It acts like a password, so it is sent in a header, never in URLs. */
export const userIdStorage = {
  get: (): string | null => localStorage.getItem(USER_ID_STORAGE_KEY),
  set: (userId: string) => localStorage.setItem(USER_ID_STORAGE_KEY, userId),
  clear: () => localStorage.removeItem(USER_ID_STORAGE_KEY),
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<ResponseBody>(
  method: string,
  path: string,
  body?: unknown,
): Promise<ResponseBody> {
  const headers: Record<string, string> = {};
  const userId = userIdStorage.get();
  if (userId) headers["X-User-Id"] = userId;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      error.code ?? "UNKNOWN",
      error.message ?? `Request failed (${response.status}).`,
    );
  }
  return (response.status === 204 ? undefined : await response.json()) as ResponseBody;
}

const channelPath = (channelId: string) => `/v1/channels/${encodeURIComponent(channelId)}`;

export const api = {
  createUser: (displayName: string) => request<User>("POST", "/v1/users", { displayName }),
  getMe: () => request<User>("GET", "/v1/users/me"),
  renameMe: (displayName: string) => request<User>("PATCH", "/v1/users/me", { displayName }),
  getMyChannels: () => request<UserChannels>("GET", "/v1/users/me/channels"),
  getMyActivity: () => request<PersonActivity>("GET", "/v1/users/me/activity"),
  markMyActivityRead: () => request<void>("POST", "/v1/users/me/activity/read"),

  createChannel: (name: string) => request<Channel>("POST", "/v1/channels", { name }),
  getChannel: (channelId: string) => request<Channel>("GET", channelPath(channelId)),
  renameChannel: (channelId: string, name: string) =>
    request<Channel>("PATCH", channelPath(channelId), { name }),
  deleteChannel: (channelId: string) => request<void>("DELETE", channelPath(channelId)),
  joinChannel: (channelId: string) =>
    request<Participant>("POST", `${channelPath(channelId)}/join`),
  leaveChannel: (channelId: string) => request<void>("POST", `${channelPath(channelId)}/leave`),

  getParticipants: (channelId: string) =>
    request<{ participants: Participant[] }>("GET", `${channelPath(channelId)}/participants`),
  removeParticipant: (channelId: string, participantId: string) =>
    request<void>("DELETE", `${channelPath(channelId)}/participants/${participantId}`),

  getMessages: (channelId: string, beforeSeq?: number) =>
    request<MessagePage>(
      "GET",
      `${channelPath(channelId)}/messages${beforeSeq ? `?before=${beforeSeq}` : ""}`,
    ),
  /** target: { threadId: "general" } for a new topic, or { replyToMessageId } for a reply. */
  sendMessage: (
    channelId: string,
    body: string,
    target: { threadId: string } | { replyToMessageId: string },
  ) =>
    request<Message>("POST", `${channelPath(channelId)}/messages`, {
      body,
      requestId: crypto.randomUUID(),
      ...target,
    }),
  deleteMessage: (channelId: string, messageId: string) =>
    request<void>("DELETE", `${channelPath(channelId)}/messages/${messageId}`),

  getThread: (channelId: string, threadId: string) =>
    request<Thread>("GET", `${channelPath(channelId)}/threads/${threadId}`),
  setFollowing: (channelId: string, threadId: string, following: boolean) =>
    request<{ threadId: string; following: boolean }>(
      "PUT",
      `${channelPath(channelId)}/threads/${threadId}/follow`,
      { following },
    ),
};

/** Links people and agents use to reach a channel. */
export function channelLinks(channelId: string) {
  const origin = window.location.origin;
  return {
    humanLink: `${origin}/c/${channelId}`,
    agentInstructionsLink: `${origin}${channelPath(channelId)}/openapi.yaml`,
    liveUpdatesUrl: `${origin.replace(/^http/, "ws")}${channelPath(channelId)}/live`,
  };
}
