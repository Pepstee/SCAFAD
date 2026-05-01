"""``/api/detections`` list / detail / summary routes.

Phase 1 surface (``severity``, ``anomaly_type``, ``function_id``, ``since``,
``page``, ``page_size``) is preserved byte-for-byte.  Phase 2 ADDS six
optional filters and an optional ``case`` field on the detail response.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..schemas import (
    CaseSummary,
    DashboardSummary,
    DetectionDetail,
    DetectionListResponse,
    DetectionSummary,
    HistogramBucket,
    SeverityMix,
)
from ..store import (
    case_to_summary_dict,
    detection_to_detail_dict,
    detection_to_summary_dict,
)


router = APIRouter(prefix="/api/detections", tags=["detections"])


@router.get("", response_model=DetectionListResponse)
def list_detections(
    request: Request,
    # ── Phase 1 filters (signature unchanged) ─────────────────────────
    severity: Optional[str] = Query(default=None),
    anomaly_type: Optional[str] = Query(default=None),
    function_id: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    # ── Phase 2 (optional, additive) ─────────────────────────────────
    until: Optional[datetime] = Query(default=None),
    mitre_technique: Optional[str] = Query(default=None),
    decision: Optional[str] = Query(default=None),
    risk_band: Optional[str] = Query(default=None),
    text: Optional[str] = Query(default=None),
    case_status: Optional[str] = Query(default=None),
) -> DetectionListResponse:
    """List detections matching the supplied filters, ordered newest-first."""

    store = request.app.state.store
    rows, total = store.list_detections(
        severity=severity,
        anomaly_type=anomaly_type,
        function_id=function_id,
        since=since,
        until=until,
        mitre_technique=mitre_technique,
        decision=decision,
        risk_band=risk_band,
        text=text,
        case_status=case_status,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    items = [DetectionSummary(**detection_to_summary_dict(r)) for r in rows]
    return DetectionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/summary", response_model=DashboardSummary)
def detections_summary(request: Request) -> DashboardSummary:
    """Aggregates that power the Operations Dashboard's KPI tiles + chart."""

    store = request.app.state.store
    adapter = request.app.state.runtime_adapter
    mix = store.severity_mix()
    hist_raw = store.histogram_24h()
    hist = [HistogramBucket(**b) for b in hist_raw]
    open_count = mix["review"] + mix["escalate"]
    return DashboardSummary(
        open_count=open_count,
        severity_mix=SeverityMix(
            observe=mix["observe"], review=mix["review"], escalate=mix["escalate"]
        ),
        ingest_rate_1h=store.ingest_rate_last_hour(),
        layer_p95_ms=adapter.latency_p95_ms(),
        hist24h=hist,
    )


@router.get("/{detection_id}", response_model=DetectionDetail)
def get_detection(request: Request, detection_id: str) -> DetectionDetail:
    """Return the full layer-by-layer evidence trail for one detection.

    Phase 2: surfaces the linked :class:`CaseSummary` (or ``null``) at the
    top level of the response.  Phase-1 callers that ignore unknown fields
    are unaffected.
    """

    store = request.app.state.store
    row = store.get_detection(detection_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"detection '{detection_id}' not found")
    payload = detection_to_detail_dict(row)
    if payload["ingested_at"].tzinfo is None:
        payload["ingested_at"] = payload["ingested_at"].replace(tzinfo=timezone.utc)
    case_row = store.case_for_detection(detection_id)
    payload["case"] = (
        CaseSummary(**case_to_summary_dict(case_row)) if case_row is not None else None
    )
    return DetectionDetail(**payload)


__all__ = ["router"]
