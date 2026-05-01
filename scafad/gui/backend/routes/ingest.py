"""``POST /api/ingest`` — drive the runtime and persist the result."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from ..audit import record_audit
from ..schemas import IngestRequest, IngestResponse
from ..store import detection_to_summary_dict
from ..users import User, get_current_user


logger = logging.getLogger("scafad.gui.routes.ingest")


router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse, status_code=201)
async def ingest_event(
    request: Request,
    payload: IngestRequest,
    user: User = Depends(get_current_user),
) -> IngestResponse:
    """Run the canonical runtime on the supplied event and persist the result.

    The endpoint returns the persisted detection's id, severity, anomaly type,
    and MITRE ATT&CK techniques.  The full evidence trail is available via
    ``GET /api/detections/{id}``.
    """

    adapter = request.app.state.runtime_adapter
    store = request.app.state.store
    bus = request.app.state.event_bus

    event: Dict[str, Any] = payload.to_event()
    if not event:
        raise HTTPException(status_code=400, detail="empty ingest payload")

    try:
        # Runtime work is CPU-bound (~200ms) and synchronous; offload so the
        # event loop remains responsive to other requests and SSE keep-alives.
        outcome = await asyncio.to_thread(adapter.ingest, event)
    except Exception as exc:  # noqa: BLE001 — defensive boundary
        logger.exception("Runtime ingest failed")
        raise HTTPException(status_code=500, detail=f"runtime failed: {exc}") from exc

    row = store.insert_detection(
        event_id=outcome.event_id or (event.get("event_id") or "ingest-event"),
        function_id=outcome.function_id,
        anomaly_type=outcome.anomaly_type,
        severity=outcome.severity,
        trust_score=outcome.trust_score,
        mitre_techniques=outcome.mitre_techniques,
        layer_payload=outcome.layer_payload,
        decision=outcome.decision,
        risk_band=outcome.risk_band,
        duration_ms=outcome.duration_ms,
        correlation_id=outcome.correlation_id,
    )

    # Best-effort SSE broadcast.  Failures here must never break the request.
    try:
        await bus.publish(detection_to_summary_dict(row), event_type="detection")
    except Exception:  # noqa: BLE001
        logger.debug("SSE publish failed", exc_info=True)

    record_audit(
        request,
        actor_id=user.id,
        subject_kind="ingest",
        subject_id=row.id,
        action="created",
        payload={
            "anomaly_type": row.anomaly_type,
            "severity": row.severity,
            "function_id": row.function_id,
        },
    )

    return IngestResponse(
        id=row.id,
        severity=row.severity,
        anomaly_type=row.anomaly_type,
        mitre_techniques=list(row.mitre_techniques),
    )


__all__ = ["router"]
