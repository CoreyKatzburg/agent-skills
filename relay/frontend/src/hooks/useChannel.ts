import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { GENERAL_THREAD_ID, type Channel, type Message, type Participant } from "../api/types";

const PARTICIPANT_REFRESH_MS = 60_000;

/** Adds or replaces a message (matched by id) and keeps the list in send order. */
export function upsertMessage(messages: Message[], changed: Message): Message[] {
  const others = messages.filter((message) => message.threadId !== changed.threadId);
  return [...others, changed].sort((a, b) => a.seq - b.seq);
}

/** Loads a channel, its participants, and its root messages, and lets callers apply live changes. */
export function useChannel(channelId: string) {
  const [channel, setChannel] = useState<Channel | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [hasOlder, setHasOlder] = useState(false);
  const [notFound, setNotFound] = useState(false);

  const refreshChannel = useCallback(
    () =>
      api
        .getChannel(channelId)
        .then(setChannel)
        .catch(() => setNotFound(true)),
    [channelId],
  );

  const refreshParticipants = useCallback(
    () =>
      api
        .getParticipants(channelId)
        .then((response) => setParticipants(response.participants))
        .catch(() => undefined),
    [channelId],
  );

  useEffect(() => {
    setChannel(null);
    setParticipants([]);
    setMessages([]);
    setNotFound(false);
    void refreshChannel();
    void refreshParticipants();
    api
      .getMessages(channelId)
      .then((page) => {
        setMessages(page.messages);
        setHasOlder(page.hasOlder);
      })
      .catch(() => setNotFound(true));
  }, [channelId, refreshChannel, refreshParticipants]);

  // Agents show as online while they keep polling, so refresh the list now and then.
  useEffect(() => {
    const timer = window.setInterval(() => void refreshParticipants(), PARTICIPANT_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [refreshParticipants]);

  const loadOlder = useCallback(async () => {
    const oldest = messages[0];
    if (!oldest) return;
    const page = await api.getMessages(channelId, oldest.seq);
    setMessages((current) => [...page.messages, ...current]);
    setHasOlder(page.hasOlder);
  }, [channelId, messages]);

  /** Apply a new or changed message. Only root messages belong in the main feed. */
  const applyMessage = useCallback((message: Message) => {
    if (message.parentThreadId !== GENERAL_THREAD_ID) return;
    setMessages((current) => upsertMessage(current, message));
  }, []);

  return {
    channel,
    participants,
    messages,
    hasOlder,
    notFound,
    loadOlder,
    applyMessage,
    refreshChannel,
    refreshParticipants,
  };
}
