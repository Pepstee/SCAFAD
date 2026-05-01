"""Process-wide pub/sub bus used by the SSE detection feed.

The bus uses :class:`asyncio.Queue` instances per subscriber.  Publishers call
:meth:`publish` from any thread; the bus thread-safely schedules the dispatch
on the bound event loop.

Phase 2 generalises the bus to carry arbitrary SSE *event types* — the
existing ``"detection"`` channel keeps emitting one frame per persisted
detection, and three new channels are added:

* ``"case"``  — case CRUD (created / updated / deleted / state-change)
* ``"bulk"``  — single coalesced frame per bulk endpoint (per ADR-15)
* ``"keepalive"`` — synthetic frame, only emitted by the SSE generator on
  timeout

Each subscriber sees a stream of ``(event_type, body)`` tuples; the SSE
route translates them into ``event: <type>\\ndata: <body>`` frames.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Tuple


logger = logging.getLogger("scafad.gui.event_bus")


SSEMessage = Tuple[str, str]
"""``(event_type, json_body)`` pairs delivered to SSE subscribers."""


class DetectionEventBus:
    """In-process broadcaster for typed SSE events."""

    def __init__(self, max_queue: int = 64) -> None:
        self._subscribers: List[asyncio.Queue[SSEMessage]] = []
        self._max_queue = int(max_queue)
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    async def subscribe(self) -> asyncio.Queue[SSEMessage]:
        queue: asyncio.Queue[SSEMessage] = asyncio.Queue(maxsize=self._max_queue)
        async with self._lock:
            self._subscribers.append(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[SSEMessage]) -> None:
        async with self._lock:
            try:
                self._subscribers.remove(queue)
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(
        self,
        payload: Dict[str, Any],
        *,
        event_type: str = "detection",
    ) -> None:
        """Asynchronously dispatch a JSON-serialised payload to subscribers.

        ``event_type`` controls which SSE channel name the route uses
        (``event: detection`` / ``event: case`` / ``event: bulk``).  Phase-1
        callers that omit the kwarg keep emitting on the ``detection``
        channel — the contract test ``test_eventbus_default_channel_is_detection``
        guards this.
        """

        body = json.dumps(payload, default=str)
        message: SSEMessage = (event_type, body)
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.debug("SSE subscriber queue full; dropping %s event", event_type)

    # Convenience wrappers ------------------------------------------------

    async def publish_detection(self, payload: Dict[str, Any]) -> None:
        await self.publish(payload, event_type="detection")

    async def publish_case(self, payload: Dict[str, Any]) -> None:
        await self.publish(payload, event_type="case")

    async def publish_bulk(self, payload: Dict[str, Any]) -> None:
        await self.publish(payload, event_type="bulk")

    def subscriber_count(self) -> int:
        return len(self._subscribers)


__all__ = ["DetectionEventBus", "SSEMessage"]
