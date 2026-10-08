import { useEffect, useRef, useState } from "react";
import { channelLinks, userIdStorage } from "../api/client";
import type { LiveEvent } from "../api/types";

const FIRST_RETRY_DELAY_MS = 1_000;
const MAX_RETRY_DELAY_MS = 15_000;

/**
 * Keeps a WebSocket open to the channel and calls onEvent for each pushed change.
 * Reconnects with a growing delay when the connection drops. Returns whether it is connected.
 *
 * memberId is only used to reconnect after joining, so the server sees you as online.
 */
export function useLiveUpdates(
  channelId: string,
  memberId: string | null,
  onEvent: (event: LiveEvent) => void,
): boolean {
  const [connected, setConnected] = useState(true);
  // Keep the latest handler without reconnecting every time it changes.
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let retryDelay = FIRST_RETRY_DELAY_MS;
    let stopped = false;

    const connect = () => {
      socket = new WebSocket(channelLinks(channelId).liveUpdatesUrl);
      socket.onopen = () => {
        // Identify ourselves in the first message instead of the URL, so the id stays out of logs.
        socket?.send(JSON.stringify({ userId: userIdStorage.get() }));
        retryDelay = FIRST_RETRY_DELAY_MS;
        setConnected(true);
      };
      socket.onmessage = (message) => onEventRef.current(JSON.parse(message.data) as LiveEvent);
      socket.onclose = () => {
        if (stopped) return;
        setConnected(false);
        retryTimer = window.setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, MAX_RETRY_DELAY_MS);
      };
    };

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, [channelId, memberId]);

  return connected;
}
