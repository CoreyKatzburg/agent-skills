import type { Message, Participant } from "../api/types";
import { formatRelative, formatTime } from "../lib/time";
import { Avatar } from "./Avatar";
import { MessageBody } from "./MessageBody";

const MAX_REPLIER_AVATARS = 4;

interface MessageItemProps {
  message: Message;
  participantsById: Map<string, Participant>;
  /** Hide the avatar and name when the same person posted just before. */
  isContinuation?: boolean;
  isMine: boolean;
  /** Omit to hide the "Reply in thread" action and reply summary (inside a thread panel). */
  onOpenThread?: () => void;
  onDelete?: () => void;
}

export function MessageItem({
  message,
  participantsById,
  isContinuation = false,
  isMine,
  onOpenThread,
  onDelete,
}: MessageItemProps) {
  const sender = participantsById.get(message.participantId);
  const senderName = sender?.displayName ?? message.senderDisplay;

  if (message.kind === "event") {
    return (
      <div className="message message--event">
        <Avatar name={senderName} kind={message.senderKind} icon={message.senderIcon} />
        <div className="message__content">
          <div className="message__header">
            <span className="message__sender">{senderName}</span>
            <time className="message__time">{formatTime(message.createdAt)}</time>
          </div>
          <p className="muted">{message.body}</p>
        </div>
      </div>
    );
  }

  return (
    <article className={`message ${isContinuation ? "message--continuation" : ""}`}>
      {isContinuation ? (
        <time className="message__gutter-time">{formatTime(message.createdAt)}</time>
      ) : (
        <Avatar name={senderName} kind={message.senderKind} icon={message.senderIcon} />
      )}
      <div className="message__content">
        {!isContinuation && (
          <div className="message__header">
            <span className="message__sender">{senderName}</span>
            {message.senderKind === "agent" && <span className="tag">agent</span>}
            <time className="message__time">{formatTime(message.createdAt)}</time>
          </div>
        )}
        {message.deleted ? (
          <p className="muted message__deleted">This message was deleted.</p>
        ) : (
          <MessageBody message={message} participantsById={participantsById} />
        )}
        {onOpenThread && message.replyCount > 0 && (
          <button type="button" className="reply-summary" onClick={onOpenThread}>
            <span className="reply-summary__avatars">
              {message.replyParticipantIds.slice(0, MAX_REPLIER_AVATARS).map((participantId) => {
                const replier = participantsById.get(participantId);
                return (
                  <Avatar
                    key={participantId}
                    name={replier?.displayName ?? participantId}
                    kind={replier?.kind ?? "agent"}
                    icon={replier?.icon}
                    size="small"
                  />
                );
              })}
            </span>
            <span className="reply-summary__count">
              {message.replyCount} {message.replyCount === 1 ? "reply" : "replies"}
            </span>
            {message.lastReplyAt && (
              <span className="muted">Last reply {formatRelative(message.lastReplyAt)}</span>
            )}
          </button>
        )}
      </div>
      {!message.deleted && (onOpenThread || (isMine && onDelete)) && (
        <div className="message__actions" aria-label="Message actions">
          {onOpenThread && (
            <button type="button" className="icon-button" title="Reply in thread" onClick={onOpenThread}>
              ↩
            </button>
          )}
          {isMine && onDelete && (
            <button type="button" className="icon-button" title="Delete message" onClick={onDelete}>
              🗑
            </button>
          )}
        </div>
      )}
    </article>
  );
}

/** True when a message should be tucked under the previous one (same sender, within 5 minutes). */
export function continuesPrevious(message: Message, previous: Message | undefined): boolean {
  if (!previous || previous.kind === "event" || message.kind === "event") return false;
  const minutesApart = (new Date(message.createdAt).getTime() - new Date(previous.createdAt).getTime()) / 60_000;
  return previous.participantId === message.participantId && minutesApart < 5;
}
