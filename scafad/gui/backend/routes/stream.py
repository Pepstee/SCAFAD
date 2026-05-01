"""Server-Sent Events feed for live detection updates.

The route emits one ``event: detection`` frame per new persistence (broadcast
by :mod:`scafad.gui.backend.routes.ingest`), one ``event: case`` per case
CRUD (Phase 2), one ``event: bulk`` per bulk-action commit (Phase 2), and a
``event: keepalive`` ping every ``settings.sse_keepalive_seconds`` seconds to
defeat reverse-proxy idle timeouts.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Dict

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse


logger = logging.getLogger("scafad.gui.routes.stream")


router = APIRouter(prefix="/api/detections", tags=["detections"])


@router.get("/stream")
async def stream_detections(request: Request) -> EventSourceResponse:
    """Open a long-lived SSE connection that broadcasts new events."""

    bus = request.app.state.event_bus
    settings = request.app.state.settings
    keepalive_seconds = float(settings.sse_keepalive_seconds)

    async def event_generator() -> AsyncIterator[Dict[str, str]]:
        queue = await bus.subscribe()
        try:
            yield {
                "event": "hello",
                "data": f'{{"ts": "{datetime.now(timezone.utc).isoformat()}"}}',
            }
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=keepalive_seconds)
                except asyncio.TimeoutError:
                    yield {"event": "keepalive", "data": "{}"}
                    continue
                # Phase-2 messages are ``(event_type, body)`` tuples.  Phase-1
                # legacy callers that put plain strings on the queue are
                # treated as ``detection`` events for backwards-compat.
                if isinstance(message, tuple) and len(message) == 2:
                    event_type, body = message
                else:  # pragma: no cover - defensive
                    event_type, body = "detection", str(message)
                yield {"event": event_type, "data": body}
        finally:
            await bus.unsubscribe(queue)
            logger.debug("SSE client disconnected; queue released")

    return EventSourceResponse(event_generator())


__all__ = ["router"]
