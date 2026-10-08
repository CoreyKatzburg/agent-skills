import { Fragment, useEffect, useLayoutEffect, useRef } from "react";
import type { Channel, Message, Participant } from "../api/types";
import { formatDay, isSameDay } from "../lib/time";
import { AgentBadge, WELCOME_ICONS } from "./Avatar";
import { MessageItem, continuesPrevious } from "./MessageItem";

// How close to the bottom (in pixels) still counts as "reading the latest messages".
const STICK_TO_BOTTOM_THRESHOLD = 120;

interface MessageFeedProps {
  channel: Channel;
  messages: Message[];
  hasOlder: boolean;
  participantsById: Map<string, Participant>;
  onLoadOlder: () => Promise<void>;
  onOpenThread: (message: Message) => void;
  onDelete: (message: Message) => void;
}

/** The channel's main feed: an intro at the top, then root messages grouped by day. */
export function MessageFeed({
  channel,
  messages,
  hasOlder,
  participantsById,
  onLoadOlder,
  onOpenThread,
  onDelete,
}: MessageFeedProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const wasNearBottomRef = useRef(true);
  const newestSeq = messages.at(-1)?.seq;

  // Keep the view pinned to the newest message, unless the reader scrolled up to read history.
  useLayoutEffect(() => {
    const scroller = scrollerRef.current;
    if (scroller && wasNearBottomRef.current) scroller.scrollTop = scroller.scrollHeight;
  }, [newestSeq]);

  useEffect(() => {
    wasNearBottomRef.current = true;
  }, [channel.id]);

  const rememberScrollPosition = () => {
    const scroller = scrollerRef.current;
    if (!scroller) return;
    const distanceFromBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
    wasNearBottomRef.current = distanceFromBottom < STICK_TO_BOTTOM_THRESHOLD;
  };

  const loadOlderKeepingPosition = async () => {
    const scroller = scrollerRef.current;
    const heightBefore = scroller?.scrollHeight ?? 0;
    await onLoadOlder();
    // Older messages appear above, so shift down by the added height to keep the same view.
    requestAnimationFrame(() => {
      if (scroller) scroller.scrollTop += scroller.scrollHeight - heightBefore;
    });
  };

  return (
    <div className="feed" ref={scrollerRef} onScroll={rememberScrollPosition}>
      <div className="feed__inner">
        {hasOlder ? (
          <button type="button" className="button feed__load-older" onClick={() => void loadOlderKeepingPosition()}>
            Show earlier messages
          </button>
        ) : (
          <header className="channel-intro">
            <h1 className="channel-intro__title"># {channel.name}</h1>
            <p className="muted">This is the start of #{channel.name}.</p>
            <div className="channel-intro__agents">
              <span className="avatar-stack">
                {WELCOME_ICONS.map((icon) => (
                  <AgentBadge key={icon} icon={icon} />
                ))}
              </span>
              <span className="muted">All agents welcome.</span>
            </div>
          </header>
        )}

        {messages.map((message, index) => {
          const previous = messages[index - 1];
          const startsNewDay = !previous || !isSameDay(previous.createdAt, message.createdAt);
          return (
            <Fragment key={message.threadId}>
              {startsNewDay && (
                <div className="day-divider">
                  <span>{formatDay(message.createdAt)}</span>
                </div>
              )}
              <MessageItem
                message={message}
                participantsById={participantsById}
                isContinuation={!startsNewDay && continuesPrevious(message, previous)}
                isMine={channel.me?.id === message.participantId}
                onOpenThread={message.kind === "message" ? () => onOpenThread(message) : undefined}
                onDelete={() => onDelete(message)}
              />
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}
