import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, api, userIdStorage } from "../api/client";
import type { User, UserChannels } from "../api/types";

const ACTIVITY_REFRESH_MS = 30_000;
const NO_CHANNELS: UserChannels = { owned: [], shared: [] };

interface Session {
  /** False until we know whether the browser already has a user. */
  ready: boolean;
  user: User | null;
  channels: UserChannels;
  unreadActivityCount: number;
  /** Returns the current user, creating one with this name if the browser has none yet. */
  ensureUser: (displayName: string) => Promise<User>;
  renameUser: (displayName: string) => Promise<void>;
  refreshChannels: () => Promise<void>;
  refreshActivityCount: () => Promise<void>;
}

const SessionContext = createContext<Session | null>(null);

/** Holds what every page needs: who you are, your channels, and your unread activity count. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [channels, setChannels] = useState<UserChannels>(NO_CHANNELS);
  const [unreadActivityCount, setUnreadActivityCount] = useState(0);

  const refreshChannels = useCallback(async () => {
    if (!userIdStorage.get()) return;
    setChannels(await api.getMyChannels());
  }, []);

  const refreshActivityCount = useCallback(async () => {
    if (!userIdStorage.get()) return;
    setUnreadActivityCount((await api.getMyActivity()).unreadCount);
  }, []);

  // Restore the user this browser used before, if any.
  useEffect(() => {
    if (!userIdStorage.get()) {
      setReady(true);
      return;
    }
    api
      .getMe()
      .then(async (me) => {
        setUser(me);
        await Promise.all([refreshChannels(), refreshActivityCount()]);
      })
      .catch((error) => {
        // The stored id is no longer valid (for example, the database was reset).
        if (error instanceof ApiError && error.status === 401) userIdStorage.clear();
      })
      .finally(() => setReady(true));
  }, [refreshChannels, refreshActivityCount]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setInterval(() => void refreshActivityCount(), ACTIVITY_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [user, refreshActivityCount]);

  const ensureUser = useCallback(
    async (displayName: string) => {
      if (user) return user;
      const created = await api.createUser(displayName);
      userIdStorage.set(created.id);
      setUser(created);
      return created;
    },
    [user],
  );

  const renameUser = useCallback(async (displayName: string) => {
    setUser(await api.renameMe(displayName));
  }, []);

  return (
    <SessionContext.Provider
      value={{
        ready,
        user,
        channels,
        unreadActivityCount,
        ensureUser,
        renameUser,
        refreshChannels,
        refreshActivityCount,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession must be used inside <SessionProvider>.");
  return session;
}
