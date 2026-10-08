import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router";
import { api } from "../api/client";
import { GENERAL_THREAD_ID, type PersonActivity } from "../api/types";
import { AppShell } from "../components/AppShell";
import { Avatar } from "../components/Avatar";
import { MessageBody } from "../components/MessageBody";
import { useSession } from "../hooks/useSession";
import { formatRelative } from "../lib/time";

/** Mentions of you, and replies in threads you follow, across all your channels. */
export function ActivityPage() {
  const { ready, user, refreshActivityCount } = useSession();
  const [activity, setActivity] = useState<PersonActivity | null>(null);

  useEffect(() => {
    if (!user) return;
    api.getMyActivity().then(async (loaded) => {
      setActivity(loaded);
      // Opening this page counts as reading everything on it.
      if (loaded.unreadCount > 0) {
        await api.markMyActivityRead();
        await refreshActivityCount();
      }
    });
  }, [user, refreshActivityCount]);

  if (ready && !user) return <Navigate to="/" replace />;

  return (
    <AppShell>
      {(showSidebarButton) => (
        <div className="activity-page">
          <header className="page-header">
            {showSidebarButton}
            <h1 className="page-header__title">Activity</h1>
          </header>
          <div className="activity-page__list">
            {activity?.items.length === 0 && (
              <p className="muted activity-page__empty">
                Nothing yet. Mentions of you and replies in threads you follow show up here.
              </p>
            )}
            {activity?.items.map((item) => {
              const { message } = item;
              const rootId =
                message.parentThreadId === GENERAL_THREAD_ID ? message.threadId : message.parentThreadId;
              return (
                <Link
                  key={message.threadId}
                  to={`/c/${item.channelId}/t/${rootId}`}
                  className={`activity-item ${item.unread ? "activity-item--unread" : ""}`}
                >
                  <Avatar name={message.senderDisplay} kind={message.senderKind} icon={message.senderIcon} />
                  <div className="activity-item__content">
                    <div className="message__header">
                      <span className="message__sender">{message.senderDisplay}</span>
                      <span className="muted">
                        {item.reasons.includes("mention") ? "mentioned you" : "replied in a thread you follow"} in #
                        {item.channelName}
                      </span>
                      <time className="message__time">{formatRelative(message.createdAt)}</time>
                    </div>
                    <MessageBody message={message} />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </AppShell>
  );
}
