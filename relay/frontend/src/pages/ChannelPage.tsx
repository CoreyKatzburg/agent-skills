import { useCallback, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api } from "../api/client";
import { GENERAL_THREAD_ID, type LiveEvent, type Message, type Participant } from "../api/types";
import { AppShell } from "../components/AppShell";
import { Composer } from "../components/Composer";
import { ConfirmDialog, TextInputDialog } from "../components/Dialog";
import { MessageFeed } from "../components/MessageFeed";
import { ShareDialog } from "../components/ShareDialog";
import { ThreadPanel } from "../components/ThreadPanel";
import { useChannel } from "../hooks/useChannel";
import { useLiveUpdates } from "../hooks/useLiveUpdates";
import { useSession } from "../hooks/useSession";
import { useThread } from "../hooks/useThread";

type OpenDialog = "share" | "rename" | "delete" | "leave" | "joinWithName" | null;

export function ChannelPage() {
  const { channelId = "", threadId } = useParams();
  const navigate = useNavigate();
  const { user, ensureUser, refreshChannels } = useSession();
  const channelState = useChannel(channelId);
  const { channel, participants, messages, hasOlder, notFound } = channelState;
  const threadState = useThread(channelId, threadId);
  const [openDialog, setOpenDialog] = useState<OpenDialog>(null);
  const [messageToDelete, setMessageToDelete] = useState<Message | null>(null);
  const channelMenuRef = useRef<HTMLDetailsElement>(null);

  const me = channel?.me ?? null;
  const participantsById = useMemo(
    () => new Map(participants.map((participant) => [participant.id, participant])),
    [participants],
  );

  const handleLiveEvent = useCallback(
    (event: LiveEvent) => {
      switch (event.type) {
        case "message":
          channelState.applyMessage(event.message);
          threadState.applyMessage(event.message);
          break;
        case "participants":
          void channelState.refreshParticipants();
          break;
        case "channel":
          void channelState.refreshChannel();
          void refreshChannels();
          break;
        case "channelDeleted":
          void refreshChannels();
          navigate("/");
          break;
      }
    },
    [channelState, threadState, refreshChannels, navigate],
  );
  const connected = useLiveUpdates(channelId, me?.id ?? null, handleLiveEvent);

  if (notFound) {
    return (
      <div className="centered-page">
        <h1>Channel unavailable</h1>
        <p className="muted">This channel may have been deleted, or the link may be incomplete.</p>
        <Link to="/" className="button">
          Back to home
        </Link>
      </div>
    );
  }

  const join = async () => {
    await api.joinChannel(channelId);
    await Promise.all([channelState.refreshChannel(), channelState.refreshParticipants(), refreshChannels()]);
  };

  const sendRootMessage = async (body: string) => {
    channelState.applyMessage(await api.sendMessage(channelId, body, { threadId: GENERAL_THREAD_ID }));
  };

  const sendReply = async (body: string) => {
    if (!threadId) return;
    const reply = await api.sendMessage(channelId, body, { replyToMessageId: threadId });
    threadState.applyMessage(reply);
    threadState.reload(); // picks up the new "following" state and reply count
  };

  const closeChannelMenu = () => channelMenuRef.current?.removeAttribute("open");

  const removeParticipant = async (participant: Participant) => {
    await api.removeParticipant(channelId, participant.id);
    await channelState.refreshParticipants();
  };

  return (
    <AppShell
      participants={participants}
      myParticipantId={me?.id}
      onRemoveParticipant={channel?.isOwner ? removeParticipant : undefined}
    >
      {(showSidebarButton) => (
        <div className="channel-page">
          <section className="channel-page__main">
            <header className="page-header">
              {showSidebarButton}
              {channel && (
                <details className="menu" ref={channelMenuRef}>
                  <summary className="page-header__title">
                    <span className="muted">#</span> {channel.name}
                  </summary>
                  <div className="menu__items" onClick={closeChannelMenu}>
                    {channel.isOwner && (
                      <>
                        <button type="button" onClick={() => setOpenDialog("rename")}>
                          Rename channel
                        </button>
                        <button type="button" className="danger" onClick={() => setOpenDialog("delete")}>
                          Delete channel
                        </button>
                      </>
                    )}
                    {!channel.isOwner && me && (
                      <button type="button" className="danger" onClick={() => setOpenDialog("leave")}>
                        Leave channel
                      </button>
                    )}
                    <button type="button" onClick={() => setOpenDialog("share")}>
                      Share channel
                    </button>
                  </div>
                </details>
              )}
              <div className="page-header__end">
                {!connected && (
                  <span className="connection-warning">
                    <span className="connection-warning__dot" /> Reconnecting…
                  </span>
                )}
                <button type="button" className="button button--small" onClick={() => setOpenDialog("share")}>
                  Share
                </button>
              </div>
            </header>

            {channel ? (
              <MessageFeed
                channel={channel}
                messages={messages}
                hasOlder={hasOlder}
                participantsById={participantsById}
                onLoadOlder={channelState.loadOlder}
                onOpenThread={(message) => navigate(`/c/${channelId}/t/${message.threadId}`)}
                onDelete={setMessageToDelete}
              />
            ) : (
              <div className="feed" aria-busy="true" />
            )}

            <footer className="channel-page__footer">
              {me ? (
                <Composer placeholder="Send a message to everyone" participants={participants} onSend={sendRootMessage} />
              ) : (
                channel && (
                  <button
                    type="button"
                    className="button button--primary"
                    onClick={() => (user ? void join() : setOpenDialog("joinWithName"))}
                  >
                    Join channel
                  </button>
                )
              )}
            </footer>
          </section>

          {threadId && (
            <ThreadPanel
              thread={threadState.thread}
              myParticipantId={me?.id ?? null}
              participants={participants}
              participantsById={participantsById}
              onReply={sendReply}
              onToggleFollow={() => void threadState.setFollowing(!threadState.thread?.following)}
              onDelete={setMessageToDelete}
              onClose={() => navigate(`/c/${channelId}`)}
            />
          )}

          {channel && openDialog === "share" && <ShareDialog channel={channel} onClose={() => setOpenDialog(null)} />}
          {channel && openDialog === "rename" && (
            <TextInputDialog
              title="Rename channel"
              label="Channel name"
              initialValue={channel.name}
              submitLabel="Save"
              maxLength={80}
              onSubmit={async (name) => {
                await api.renameChannel(channelId, name);
                await Promise.all([channelState.refreshChannel(), refreshChannels()]);
              }}
              onClose={() => setOpenDialog(null)}
            />
          )}
          {channel && openDialog === "delete" && (
            <ConfirmDialog
              title={`Delete #${channel.name}?`}
              explanation="Everyone loses the channel and all of its messages. You can't undo this."
              confirmLabel="Delete channel"
              onConfirm={async () => {
                await api.deleteChannel(channelId);
                await refreshChannels();
                navigate("/");
              }}
              onClose={() => setOpenDialog(null)}
            />
          )}
          {channel && openDialog === "leave" && (
            <ConfirmDialog
              title={`Leave #${channel.name}?`}
              explanation="The channel disappears from your list. Your messages stay, and opening the link again lets you rejoin."
              confirmLabel="Leave channel"
              onConfirm={async () => {
                await api.leaveChannel(channelId);
                await refreshChannels();
                navigate("/");
              }}
              onClose={() => setOpenDialog(null)}
            />
          )}
          {openDialog === "joinWithName" && (
            <TextInputDialog
              title="Join channel"
              label="Your name"
              placeholder="What should we call you?"
              submitLabel="Join"
              onSubmit={async (name) => {
                await ensureUser(name);
                await join();
              }}
              onClose={() => setOpenDialog(null)}
            />
          )}
          {messageToDelete && (
            <ConfirmDialog
              title="Delete message?"
              explanation="The message is removed for everyone. Replies under it stay."
              confirmLabel="Delete"
              onConfirm={() => api.deleteMessage(channelId, messageToDelete.threadId)}
              onClose={() => setMessageToDelete(null)}
            />
          )}
        </div>
      )}
    </AppShell>
  );
}
