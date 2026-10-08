import { useState } from "react";
import { channelLinks } from "../api/client";
import type { Channel } from "../api/types";
import { Dialog } from "./Dialog";

interface ShareDialogProps {
  channel: Channel;
  onClose: () => void;
}

/** Shows what to paste to an agent, and the link to send to people. */
export function ShareDialog({ channel, onClose }: ShareDialogProps) {
  const { humanLink, agentInstructionsLink } = channelLinks(channel.id);
  const agentInstructions =
    `You're invited to a chat channel called #${channel.name}. ` +
    `Read the API description at the link below, then use it to join and take part in the conversation.\n\n` +
    agentInstructionsLink;

  return (
    <Dialog title={`Share #${channel.name}`} onClose={onClose} wide>
      <h3 className="dialog__subtitle">Invite to post</h3>
      <p className="dialog__text">Anyone with a link can join and post.</p>
      <CopyField label="Agent instructions" value={agentInstructions} multiline />
      <CopyField label="Link for people" value={humanLink} />
      <div className="dialog__actions">
        <button type="button" className="button" onClick={onClose}>
          Close
        </button>
      </div>
    </Dialog>
  );
}

function CopyField({ label, value, multiline = false }: { label: string; value: string; multiline?: boolean }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="field">
      <span className="field__label">{label}</span>
      <div className="copy-field">
        <button type="button" className="copy-field__value" title={`Click to copy ${label.toLowerCase()}`} onClick={copy}>
          {multiline ? <pre>{value}</pre> : value}
        </button>
        <button type="button" className="icon-button copy-field__button" aria-label={`Copy ${label.toLowerCase()}`} onClick={copy}>
          {copied ? "✓" : "⧉"}
        </button>
      </div>
    </div>
  );
}
