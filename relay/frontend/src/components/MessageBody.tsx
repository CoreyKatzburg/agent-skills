import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message, Participant } from "../api/types";

const MENTION_LINK_PREFIX = "#mention:";

interface MessageBodyProps {
  message: Message;
  /** The channel's current participants, so renamed people show their newest name. Optional. */
  participantsById?: Map<string, Participant>;
}

/**
 * Renders a message's Markdown safely: raw HTML shows as plain text, links open in a new tab,
 * and images become links (so viewing a message never loads anything from another server).
 * Mentions ("@<participant id>") show as chips with the participant's current name.
 */
export function MessageBody({ message, participantsById }: MessageBodyProps) {
  const components: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith(MENTION_LINK_PREFIX)) {
        return <span className="mention">{children}</span>;
      }
      return (
        <a href={href} target="_blank" rel="noreferrer noopener">
          {children}
        </a>
      );
    },
    img: ({ src, alt }) => (
      <a href={typeof src === "string" ? src : undefined} target="_blank" rel="noreferrer noopener">
        {alt || "image"}
      </a>
    ),
  };

  return (
    <div className="markdown">
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {linkMentions(message, participantsById)}
      </Markdown>
    </div>
  );
}

/** Turns each "@<participant id>" into a special Markdown link that the renderer shows as a chip. */
function linkMentions(message: Message, participantsById?: Map<string, Participant>): string {
  let linked = message.body;
  // Longest ids first, so "@ann-lee-1" is not mistaken for "@ann".
  const idsLongestFirst = [...message.mentionParticipantIds].sort((a, b) => b.length - a.length);
  for (const participantId of idsLongestFirst) {
    const name =
      participantsById?.get(participantId)?.displayName ?? message.mentionNames[participantId] ?? participantId;
    const escapedName = name.replace(/[[\]\\]/g, "\\$&");
    linked = linked.replace(
      new RegExp(`@${escapeRegExp(participantId)}(?![\\w-])`, "g"),
      `[@${escapedName}](${MENTION_LINK_PREFIX}${participantId})`,
    );
  }
  return linked;
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
