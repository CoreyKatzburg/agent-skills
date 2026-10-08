import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Message, Thread } from "../api/types";
import { upsertMessage } from "./useChannel";

/** Loads the open thread (if any) and lets callers apply live changes to it. */
export function useThread(channelId: string, threadId: string | undefined) {
  const [thread, setThread] = useState<Thread | null>(null);

  const reload = useCallback(() => {
    if (!threadId) return;
    api
      .getThread(channelId, threadId)
      .then(setThread)
      .catch(() => setThread(null));
  }, [channelId, threadId]);

  useEffect(() => {
    setThread(null);
    reload();
  }, [reload]);

  const applyMessage = useCallback((message: Message) => {
    setThread((current) => {
      if (!current) return current;
      if (message.threadId === current.root.threadId) return { ...current, root: message };
      if (message.parentThreadId !== current.root.threadId) return current;
      return { ...current, replies: upsertMessage(current.replies, message) };
    });
  }, []);

  const setFollowing = useCallback(
    async (following: boolean) => {
      if (!threadId) return;
      await api.setFollowing(channelId, threadId, following);
      setThread((current) => (current ? { ...current, following } : current));
    },
    [channelId, threadId],
  );

  return { thread, reload, applyMessage, setFollowing };
}
