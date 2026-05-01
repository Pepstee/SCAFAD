"""``/api/health`` and ``/api/system/status`` routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Request

from ..config import GUISettings
from ..schemas import HealthResponse, LayerStatus, SystemStatusResponse


router = APIRouter(prefix="/api", tags=["system"])


_LAYER_DESCRIPTIONS = [
    ("layer0", "Adaptive Telemetry Controller (26 detectors, IsolationForest, signing)"),
    ("layer1", "Canonical Validation, Sanitisation, Privacy & Hashing"),
    ("layer2", "Multi-Vector Detection Matrix (rules + drift + graph + semantic)"),
    ("layer3", "Trust-Weighted Fusion Engine"),
    ("layer4", "Explainability & Decision Trace"),
    ("layer5", "Threat Alignment (MITRE ATT&CK)"),
    ("layer6", "Feedback & Learning Engine"),
]


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    """Liveness probe with version, commit, env label, and start time.

    Used by the frontend on app boot to display the EnvBadge and "version"
    chip in the TopBar.
    """

    settings: GUISettings = request.app.state.settings
    started_at: datetime = request.app.state.started_at
    return HealthResponse(
        ok=True,
        version=settings.version,
        commit=settings.commit,
        started_at=started_at,
        env=settings.env,
        db_path=str(settings.db_path),
    )


@router.get("/system/status", response_model=SystemStatusResponse)
def get_system_status(request: Request) -> SystemStatusResponse:
    """Lightweight per-layer health snapshot.

    Phase 1 reports static layer descriptions plus three live counters
    (detector count, db size, last ingest at).  Phase 4 will wire real
    per-layer latencies and error rates here.
    """

    store = request.app.state.store
    layers: List[LayerStatus] = [
        LayerStatus(
            layer=name, healthy=True, description=description, detector_count=0
        )
        for name, description in _LAYER_DESCRIPTIONS
    ]
    # L0 carries the full detector panel.
    layers[0].detector_count = 26

    last = store.last_ingest_at()
    return SystemStatusResponse(
        layers=layers,
        detector_count=26,
        db_size_bytes=store.db_size_bytes(),
        last_ingest_at=last.astimezone(timezone.utc) if last else None,
        detections_total=store.total_count(),
    )


__all__ = ["router"]
