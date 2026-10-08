"""Live updates: pushes changes to open browser tabs and wakes agents waiting for messages.

Everything here lives in memory, so it only works with a single server process. That is
fine for a team tool; running several processes would need a shared message bus instead.
"""

import asyncio
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any


class ChannelHub:
    def __init__(self) -> None:
        self._event_loop: asyncio.AbstractEventLoop | None = None
        # channel id -> one queue per open browser connection
        self._browser_queues: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        # channel id -> participant id -> number of open browser connections
        self._online_people: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # channel id -> futures that agents waiting for new activity are sleeping on
        self._activity_waiters: dict[str, set[asyncio.Future[None]]] = defaultdict(set)

    def start(self) -> None:
        """Call once at startup, from the server's event loop."""
        self._event_loop = asyncio.get_running_loop()

    def publish(self, channel_id: str, event: dict[str, Any]) -> None:
        """Send an event to everyone watching a channel.

        Safe to call from any thread. Sync route handlers run on worker threads, so the
        actual delivery is handed over to the event loop thread.
        """
        if self._event_loop is None:
            return
        self._event_loop.call_soon_threadsafe(self._deliver, channel_id, event)

    def _deliver(self, channel_id: str, event: dict[str, Any]) -> None:
        for queue in self._browser_queues[channel_id]:
            queue.put_nowait(event)
        for waiter in self._activity_waiters[channel_id]:
            if not waiter.done():
                waiter.set_result(None)

    def connect_browser(self, channel_id: str, participant_id: str | None) -> asyncio.Queue:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._browser_queues[channel_id].add(queue)
        if participant_id:
            self._online_people[channel_id][participant_id] += 1
        return queue

    def disconnect_browser(
        self, channel_id: str, participant_id: str | None, queue: asyncio.Queue
    ) -> None:
        self._browser_queues[channel_id].discard(queue)
        if participant_id:
            self._online_people[channel_id][participant_id] -= 1
            if self._online_people[channel_id][participant_id] <= 0:
                del self._online_people[channel_id][participant_id]

    def online_participant_ids(self, channel_id: str) -> set[str]:
        return set(self._online_people[channel_id])

    @contextmanager
    def watch_for_activity(self, channel_id: str) -> Generator[asyncio.Future[None]]:
        """Gives a future that completes the next time anything is published to the channel.

        Start watching *before* checking the database. Then a message that arrives between
        the check and the wait still wakes the waiter instead of being missed.
        """
        waiter: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._activity_waiters[channel_id].add(waiter)
        try:
            yield waiter
        finally:
            self._activity_waiters[channel_id].discard(waiter)


hub = ChannelHub()
