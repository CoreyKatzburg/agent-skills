import type { AgentIcon, ParticipantKind } from "../api/types";

// Agents show a short label and color for the model or provider they run on.
// These are plain letter badges, not company logos.
const AGENT_BADGES: Record<AgentIcon, { label: string; color: string }> = {
  openai: { label: "OA", color: "#10a37f" },
  anthropic: { label: "An", color: "#d97757" },
  google: { label: "G", color: "#4c8df6" },
  xai: { label: "x", color: "#9a9aa2" },
  deepseek: { label: "DS", color: "#5b6ef5" },
  meta: { label: "M", color: "#2f7bf6" },
  mistral: { label: "Mi", color: "#f2a33a" },
  qwen: { label: "Q", color: "#7b61ff" },
  cohere: { label: "Co", color: "#39a275" },
  perplexity: { label: "Px", color: "#20b8cd" },
  microsoft: { label: "MS", color: "#00a4ef" },
  amazon: { label: "Az", color: "#ff9900" },
  nvidia: { label: "NV", color: "#76b900" },
  moonshot: { label: "Ki", color: "#a4a4ff" },
  zhipu: { label: "Z", color: "#3d6fff" },
  minimax: { label: "MM", color: "#f0506e" },
  robot: { label: "", color: "#9a9aa2" },
};

/** The icons shown in a channel's intro to say any agent can join. */
export const WELCOME_ICONS: AgentIcon[] = ["openai", "anthropic", "google", "meta", "mistral", "deepseek"];

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? "?").slice(0, 1);
  return letters.toUpperCase();
}

interface AvatarProps {
  name: string;
  kind: ParticipantKind;
  icon?: AgentIcon | null;
  size?: "small" | "medium";
  online?: boolean;
}

export function Avatar({ name, kind, icon, size = "medium", online }: AvatarProps) {
  const badge = kind === "agent" ? AGENT_BADGES[icon ?? "robot"] : null;
  return (
    <span
      className={`avatar avatar--${size}`}
      style={badge ? { color: badge.color, borderColor: badge.color } : undefined}
      title={badge && icon ? `${name} (${icon})` : name}
    >
      {badge ? badge.label || <RobotIcon /> : initials(name)}
      {online !== undefined && (
        <span className={`avatar__status ${online ? "avatar__status--online" : ""}`} aria-label={online ? "Online" : "Offline"} />
      )}
    </span>
  );
}

export function AgentBadge({ icon }: { icon: AgentIcon }) {
  return <Avatar name={icon} kind="agent" icon={icon} size="small" />;
}

function RobotIcon() {
  return (
    <svg viewBox="0 0 16 16" width="60%" height="60%" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
      <rect x="2.5" y="5" width="11" height="8" rx="2" />
      <path d="M8 2.5V5M5.5 9h.01M10.5 9h.01" strokeLinecap="round" />
    </svg>
  );
}
