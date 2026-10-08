import { useEffect, useRef } from "react";
import type { Message, Participant, Thread } from "../api/types";
import { Composer } from "./Composer";
import { MessageItem, continuesPrevious } from "./MessageItem";

interface ThreadPanelProps {
  thread: Thread | null;
  myParticipantId: string | null;
  participants: Participant[];
  participantsById: Map<string, Participant>;
  onReply: (body: string) => Promise<void>;
  onToggleFollow: () => void;
  onDelete: (message: Message) => void;
  onClose: () => void;
}

/** The side panel showing one message and its replies. */
export function ThreadPanel({
  thread,
  myParticipantId,
  participants,
  participantsById,
  onReply,
  onToggleFollow,
  onDelete,
  onClose,
}: ThreadPanelProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const replyCount = thread?.replies.length ?? 0;

  useEffect(() => {
    const scroller = scrollerRef.current;
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  }, [replyCount]);

  return (
    <aside className="thread-panel" aria-label="Thread">
      <header className="thread-panel__header">
        <h2>Thread</h2>
        <div className="thread-panel__header-actions">
          {thread && myParticipantId && (
            <button type="button" className="button button--small" onClick={onToggleFollow}>
              {thread.following ? "Following" : "Follow"}
            </button>
          )}
          <button type="button" className="icon-button" aria-label="Close thread" onClick={onClose}>
            ✕
          </button>
        </div>
      </header>

      <div className="thread-panel__messages" ref={scrollerRef}>
        {!thread ? (
          <p className="muted thread-panel__loading">Loading…</p>
        ) : (
          <>
            <MessageItem
              message={thread.root}
              participantsById={participantsById}
              isMine={thread.root.participantId === myParticipantId}
              onDelete={() => onDelete(thread.root)}
            />
            <div className="day-divider">
              <span>
                {replyCount} {replyCount === 1 ? "reply" : "replies"}
              </span>
            </div>
            {thread.replies.map((reply, index) => (
              <MessageItem
                key={reply.threadId}
                message={reply}
                participantsById={participantsById}
                isContinuation={continuesPrevious(reply, thread.replies[index - 1])}
                isMine={reply.participantId === myParticipantId}
                onDelete={() => onDelete(reply)}
              />
            ))}
          </>
        )}
      </div>

      {thread && myParticipantId && (
        <div className="thread-panel__composer">
          <Composer placeholder="Reply…" participants={participants} onSend={onReply} />
        </div>
      )}
    </aside>
  );
}
