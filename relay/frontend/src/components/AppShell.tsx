import { useState, type ReactNode } from "react";
import type { Participant } from "../api/types";
import { Sidebar } from "./Sidebar";

const NARROW_SCREEN = "(max-width: 760px)";

interface AppShellProps {
  participants?: Participant[];
  myParticipantId?: string | null;
  onRemoveParticipant?: (participant: Participant) => Promise<void>;
  /** Receives a button that brings back the hidden sidebar, to place in the page header. */
  children: (showSidebarButton: ReactNode) => ReactNode;
}

/** The sidebar plus the page beside it. The sidebar can be hidden; it starts hidden on phones. */
export function AppShell({ participants, myParticipantId, onRemoveParticipant, children }: AppShellProps) {
  const [sidebarVisible, setSidebarVisible] = useState(() => !window.matchMedia(NARROW_SCREEN).matches);

  const showSidebarButton = sidebarVisible ? null : (
    <button
      type="button"
      className="icon-button"
      aria-label="Show sidebar"
      title="Show sidebar"
      onClick={() => setSidebarVisible(true)}
    >
      ☰
    </button>
  );

  return (
    <div className="app-shell">
      {sidebarVisible && (
        <Sidebar
          participants={participants}
          myParticipantId={myParticipantId}
          onRemoveParticipant={onRemoveParticipant}
          onHide={() => setSidebarVisible(false)}
        />
      )}
      <main className="app-shell__main">{children(showSidebarButton)}</main>
    </div>
  );
}
