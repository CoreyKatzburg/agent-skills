export function formatTime(isoTime: string): string {
  return new Date(isoTime).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** "Today", "Yesterday", or a date like "Mon, Oct 6". */
export function formatDay(isoTime: string): string {
  const date = new Date(isoTime);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return "Today";
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
  return date.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}

export function isSameDay(firstIsoTime: string, secondIsoTime: string): boolean {
  return new Date(firstIsoTime).toDateString() === new Date(secondIsoTime).toDateString();
}

/** "just now", "5m ago", "3h ago", or a day. */
export function formatRelative(isoTime: string): string {
  const minutes = Math.floor((Date.now() - new Date(isoTime).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (minutes < 24 * 60) return `${Math.floor(minutes / 60)}h ago`;
  return formatDay(isoTime);
}
