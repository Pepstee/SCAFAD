"""FastAPI app factory for the SCAFAD analyst console backend.

Run locally with::

    uvicorn scafad.gui.backend.main:app --reload --host 127.0.0.1 --port 8088

or via the convenience entrypoint::

    python -m scafad.gui.backend.main
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Bootstrap sys.path to mirror the repo's pytest config; this lets the GUI
# backend be launched from anywhere without prepending PYTHONPATH manually.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCAFAD_PKG = _REPO_ROOT / "scafad"
for _p in (str(_REPO_ROOT), str(_SCAFAD_PKG)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from .config import GUISettings, get_settings  # noqa: E402
from .event_bus import DetectionEventBus  # noqa: E402
from .routes import (  # noqa: E402
    audit,
    aws_live,
    cases,
    detections,
    functions,
    health,
    inbox,
    ingest,
    settings_view,
    stream,
    system,
    threat_map,
    views,
)
from .runtime_adapter import GUIRuntimeAdapter  # noqa: E402
from .store import DetectionStore  # noqa: E402


logger = logging.getLogger("scafad.gui.main")


def create_app(settings: GUISettings | None = None) -> FastAPI:
    """Build a fresh FastAPI app instance.

    The factory accepts an explicit ``settings`` argument so tests can pin the
    SQLite path to a temporary directory without leaking state between cases.
    """

    settings = settings or get_settings()
    settings.ensure_db_directory()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # pragma: no cover
        logger.info(
            "GUI backend starting on %s:%s — env=%s db=%s",
            settings.host,
            settings.port,
            settings.env,
            settings.db_path,
        )
        yield
        logger.info("GUI backend shutting down")

    app = FastAPI(
        title="SCAFAD Analyst Console API",
        version=settings.version,
        description=(
            "HTTP surface around the SCAFAD canonical runtime. Provides "
            "detection persistence, dashboard aggregates, and an SSE feed "
            "for the analyst console UI."
        ),
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.started_at = datetime.now(timezone.utc)
    app.state.store = DetectionStore(settings.db_path)
    app.state.runtime_adapter = GUIRuntimeAdapter()
    app.state.event_bus = DetectionEventBus(max_queue=settings.sse_max_history)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    app.include_router(health.router)
    # Phase 4: register system, settings_view, audit before stream so that
    # /api/system/..., /api/settings/..., and /api/audit/... are matched
    # before any more generic paths (per architecture doc §4.4).
    app.include_router(system.router)
    app.include_router(settings_view.router)
    app.include_router(audit.router)
    # NB: ``stream.router`` MUST be registered before ``detections.router`` so
    # that ``/api/detections/stream`` is matched before
    # ``/api/detections/{detection_id}`` (FastAPI matches in registration order).
    app.include_router(stream.router)
    # Phase 2: register cases, views, inbox before detections so
    # ``/api/inbox/...`` and ``/api/cases/...`` are not shadowed by other
    # path matchers.
    # Phase 3: register functions, threat_map before detections for same reason.
    app.include_router(cases.router)
    app.include_router(views.router)
    app.include_router(inbox.router)
    app.include_router(functions.router)
    app.include_router(threat_map.router)
    # ``ingest`` is intentionally kept last so the POST /api/ingest path stays distinct.
    app.include_router(detections.router)
    app.include_router(ingest.router)
    app.include_router(aws_live.router)

    return app


# Module-level instance used by ``uvicorn scafad.gui.backend.main:app``.
app = create_app()


def _main() -> None:  # pragma: no cover - manual launcher
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "scafad.gui.backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":  # pragma: no cover
    run()
