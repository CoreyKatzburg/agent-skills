import { useState } from "react";
import { NavLink, useNavigate } from "react-router";
import { api } from "../api/client";
import type { ChannelSummary, Participant } from "../api/types";
import { useSession } from "../hooks/useSession";
import { APP_NAME, Logo } from "./Logo";
import { Avatar } from "./Avatar";
import { ConfirmDialog, TextInputDialog } from "./Dialog";

interface SidebarProps {
  /** The open channel's participants. Omit outside a channel. */
  participants?: Participant[];
  myParticipantId?: string | null;
  /** Owners can remove participants. */
  onRemoveParticipant?: (participant: Participant) => Promise<void>;
  onHide: () => void;
}

export function Sidebar({ participants, myParticipantId, onRemoveParticipant, onHide }: SidebarProps) {
  const { user, channels, unreadActivityCount, renameUser, refreshChannels } = useSession();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<"newChannel" | "renameAccount" | null>(null);
  const [participantToRemove, setParticipantToRemove] = useState<Participant | null>(null);

  const createChannel = async (name: string) => {
    const channel = await api.createChannel(name);
    await refreshChannels();
    navigate(`/c/${channel.id}`);
  };

  return (
    <nav className="sidebar" aria-label="Channels">
      <div className="sidebar__top">
        <NavLink to="/" className="brand" aria-label={`${APP_NAME} home`}>
          <Logo />
          {APP_NAME}
        </NavLink>
        <button type="button" className="icon-button" aria-label="Hide sidebar" title="Hide sidebar" onClick={onHide}>
          ⇤
        </button>
      </div>

      <div className="sidebar__scroll">
        {user && (
          <NavLink to="/activity" className="sidebar__link">
            <span aria-hidden>🔔</span> Activity
            {unreadActivityCount > 0 && <span className="badge">{unreadActivityCount}</span>}
          </NavLink>
        )}

        <SidebarSection
          title="Channels"
          action={
            user && (
              <button
                type="button"
                className="icon-button"
                aria-label="New channel"
                title="New channel"
                onClick={() => setDialog("newChannel")}
              >
                +
              </button>
            )
          }
        >
          <ChannelLinks channels={channels.owned} />
        </SidebarSection>

        {channels.shared.length > 0 && (
          <SidebarSection title="Shared with me">
            <ChannelLinks channels={channels.shared} />
          </SidebarSection>
        )}

        {participants && (
          <SidebarSection title="Participants">
            {participants.length === 0 && <p className="muted sidebar__empty">No one has joined yet.</p>}
            {participants.map((participant) => (
              <div key={participant.id} className="participant">
                <Avatar
                  name={participant.displayName}
                  kind={participant.kind}
                  icon={participant.icon}
                  size="small"
                  online={participant.online}
                />
                <span className="participant__name" title={participant.id}>
                  {participant.displayName}
                </span>
                {participant.id === myParticipantId && <span className="muted">you</span>}
                {onRemoveParticipant && participant.id !== myParticipantId && (
                  <button
                    type="button"
                    className="icon-button participant__remove"
                    title="Remove from channel"
                    aria-label={`Remove ${participant.displayName} from channel`}
                    onClick={() => setParticipantToRemove(participant)}
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </SidebarSection>
        )}
      </div>

      {user && (
        <button
          type="button"
          className="sidebar__account"
          aria-label="Change your account name"
          onClick={() => setDialog("renameAccount")}
        >
          <Avatar name={user.displayName} kind="person" size="small" />
          <span>{user.displayName}</span>
        </button>
      )}

      {dialog === "newChannel" && (
        <TextInputDialog
          title="Create a new channel"
          label="Channel name"
          placeholder="Design review"
          submitLabel="Create channel"
          maxLength={80}
          onSubmit={createChannel}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === "renameAccount" && user && (
        <TextInputDialog
          title="Your account name"
          label="Name"
          initialValue={user.displayName}
          submitLabel="Save"
          onSubmit={renameUser}
          onClose={() => setDialog(null)}
        />
      )}
      {participantToRemove && onRemoveParticipant && (
        <ConfirmDialog
          title={`Remove ${participantToRemove.displayName}?`}
          explanation="They are taken out of the channel right away. What they already posted stays. Since anyone with the link can join, they could come back later."
          confirmLabel="Remove from channel"
          onConfirm={() => onRemoveParticipant(participantToRemove)}
          onClose={() => setParticipantToRemove(null)}
        />
      )}
    </nav>
  );
}

function SidebarSection({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="sidebar__section">
      <div className="sidebar__section-header">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function ChannelLinks({ channels }: { channels: ChannelSummary[] }) {
  return channels.map((channel) => (
    <NavLink key={channel.id} to={`/c/${channel.id}`} className="sidebar__link">
      <span className="muted">#</span> {channel.name}
    </NavLink>
  ));
}
