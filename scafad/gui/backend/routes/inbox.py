"""``/api/inbox`` — inbox aggregates, bulk actions, and CSV export (Phase 2).

Endpoints
---------

* ``GET  /api/inbox/summary``     — filter-aware aggregates (severity counts,
  case-status rollup, top-N MITRE techniques)
* ``POST /api/inbox/bulk_action`` — multi-row mutation (assign / dismiss /
  attach to existing case / open new case from selection); returns a per-item
  ``BulkActionResponse`` and emits a single coalesced ``event: bulk`` SSE
  frame per ADR-15.
* ``GET  /api/inbox/export.csv``  — streams the active filter as UTF-8 CSV.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ..audit import record_audit
from ..schemas import (
    BulkActionRequest,
    BulkActionResponse,
    BulkActionResult,
    CaseStatusCounts,
    InboxSummary,
    SeverityMix,
    TechniqueCount,
)
from ..store import (
    AlreadyAttached,
    DetectionStore,
    DuplicateAttachment,
    NotFound,
    StoreError,
    case_to_summary_dict,
)
from ..users import User, get_current_user


logger = logging.getLogger("scafad.gui.routes.inbox")


router = APIRouter(prefix="/api/inbox", tags=["inbox"])


# ---------------------------------------------------------------------------
# Filter-parsing helpers (shared with /api/detections)
# ---------------------------------------------------------------------------


def _parse_filters(
    *,
    severity: Optional[str],
    anomaly_type: Optional[str],
    function_id: Optional[str],
    since: Optional[datetime],
    until: Optional[datetime],
    mitre_technique: Optional[str],
    decision: Optional[str],
    risk_band: Optional[str],
    text: Optional[str],
    case_status: Optional[str],
) -> Dict[str, Any]:
    return {
        "severity": severity,
        "anomaly_type": anomaly_type,
        "function_id": function_id,
        "since": since,
        "until": until,
        "mitre_technique": mitre_technique,
        "decision": decision,
        "risk_band": risk_band,
        "text": text,
        "case_status": case_status,
    }


# ---------------------------------------------------------------------------
# /api/inbox/summary
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=InboxSummary)
def inbox_summary(
    request: Request,
    severity: Optional[str] = Query(default=None),
    anomaly_type: Optional[str] = Query(default=None),
    function_id: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    mitre_technique: Optional[str] = Query(default=None),
    decision: Optional[str] = Query(default=None),
    risk_band: Optional[str] = Query(default=None),
    text: Optional[str] = Query(default=None),
    case_status: Optional[str] = Query(default=None),
    top_mitre: int = Query(default=8, ge=0, le=50),
) -> InboxSummary:
    """Filter-aware aggregates for the Inbox sticky header."""

    store: DetectionStore = request.app.state.store
    filters = _parse_filters(
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
    )
    # Pull the filtered slice in a single page (cap at the rolling demo
    # window — the UI uses the page-aware list endpoint for table data).
    rows, total = store.list_detections(**filters, limit=10_000, offset=0)

    # Severity mix.
    severity_counter: Dict[str, int] = {"observe": 0, "review": 0, "escalate": 0}
    for row in rows:
        sev = (row.severity or "observe").lower()
        if sev in severity_counter:
            severity_counter[sev] += 1

    # MITRE rollup.
    technique_counter: Counter[str] = Counter()
    for row in rows:
        technique_counter.update(row.mitre_techniques)
    top = [
        TechniqueCount(technique=t, count=c)
        for t, c in technique_counter.most_common(top_mitre)
    ]

    # Case-status rollup — joins per detection.
    case_counts = CaseStatusCounts()
    if rows:
        ids = [r.id for r in rows]
        # Single round-trip: fetch all (detection_id, case_status) pairs.
        with store._lock, store._connect() as conn:  # noqa: SLF001 — internal helper
            placeholders = ",".join("?" for _ in ids)
            mapped = {
                r["detection_id"]: r["status"]
                for r in conn.execute(
                    f"""
                    SELECT cd.detection_id, c.status
                    FROM case_detections cd
                    JOIN cases c ON c.id = cd.case_id
                    WHERE cd.detection_id IN ({placeholders})
                    """,
                    tuple(ids),
                ).fetchall()
            }
        for row in rows:
            status = mapped.get(row.id)
            if status == "open":
                case_counts.open += 1
            elif status == "triage":
                case_counts.triage += 1
            elif status == "contained":
                case_counts.contained += 1
            elif status == "closed":
                case_counts.closed += 1
            else:
                case_counts.none += 1

    return InboxSummary(
        total=total,
        severity_counts=SeverityMix(**severity_counter),
        case_status_counts=case_counts,
        top_mitre=top,
    )


# ---------------------------------------------------------------------------
# /api/inbox/bulk_action
# ---------------------------------------------------------------------------


@router.post("/bulk_action", response_model=BulkActionResponse)
async def bulk_action(
    request: Request,
    body: BulkActionRequest,
    user: User = Depends(get_current_user),
) -> BulkActionResponse:
    """Apply ``body.action`` to each id in ``body.detection_ids``.

    Per ADR-11 each item is attempted independently; per-item failures are
    reported in the response.  Per ADR-15 a single ``event: bulk`` SSE frame
    is emitted after commit.
    """

    store: DetectionStore = request.app.state.store
    bus = getattr(request.app.state, "event_bus", None)

    detection_ids = list(body.detection_ids)
    if not detection_ids:
        raise HTTPException(status_code=422, detail="detection_ids must not be empty")

    results: List[BulkActionResult] = []
    succeeded = 0
    failed = 0
    case_id: Optional[str] = None

    if body.action == "open_case":
        title = str(body.payload.get("title") or "New case")
        assignee_id = body.payload.get("assignee_id")
        try:
            row = store.create_case(
                title=title,
                created_by=user.id,
                detection_ids=detection_ids,
                assignee_id=assignee_id,
            )
            case_id = row.id
            for did in detection_ids:
                results.append(BulkActionResult(id=did, ok=True))
            succeeded = len(detection_ids)
        except (AlreadyAttached, StoreError) as exc:
            for did in detection_ids:
                results.append(BulkActionResult(id=did, ok=False, error=str(exc)))
            failed = len(detection_ids)
    elif body.action == "attach":
        case_id = body.payload.get("case_id")
        if not case_id:
            raise HTTPException(status_code=422, detail="payload.case_id required")
        if store.get_case(case_id) is None:
            raise HTTPException(status_code=404, detail=f"case '{case_id}' not found")
        for did in detection_ids:
            try:
                store.attach_detection(case_id, did, actor_id=user.id)
                results.append(BulkActionResult(id=did, ok=True))
                succeeded += 1
            except (AlreadyAttached, DuplicateAttachment, NotFound, StoreError) as exc:
                results.append(BulkActionResult(id=did, ok=False, error=str(exc)))
                failed += 1
    elif body.action == "assign":
        # For Phase-2 we record the assignment on each detection's currently
        # linked case (if any).  Detections without a case are reported as
        # "no_case".  Phase 5 will add direct per-detection assignment.
        assignee_id = body.payload.get("assignee_id")
        for did in detection_ids:
            case_for = store.case_for_detection(did)
            if case_for is None:
                results.append(
                    BulkActionResult(id=did, ok=False, error="no_case_attached")
                )
                failed += 1
                continue
            try:
                store.update_case(
                    case_for.id,
                    expected_version=case_for.version,
                    actor_id=user.id,
                    assignee_id=assignee_id,
                )
                results.append(BulkActionResult(id=did, ok=True))
                succeeded += 1
            except StoreError as exc:
                results.append(BulkActionResult(id=did, ok=False, error=str(exc)))
                failed += 1
    elif body.action == "dismiss":
        reason = str(body.payload.get("reason") or "")
        for did in detection_ids:
            case_for = store.case_for_detection(did)
            if case_for is None:
                # No case to dismiss; record as no-op.
                results.append(BulkActionResult(id=did, ok=True))
                succeeded += 1
                continue
            try:
                store.update_case(
                    case_for.id,
                    expected_version=case_for.version,
                    actor_id=user.id,
                    status="closed",
                    reason=reason or "dismissed",
                )
                results.append(BulkActionResult(id=did, ok=True))
                succeeded += 1
            except StoreError as exc:
                results.append(BulkActionResult(id=did, ok=False, error=str(exc)))
                failed += 1
    else:  # pragma: no cover - defended by Pydantic
        raise HTTPException(status_code=400, detail="unknown action")

    response = BulkActionResponse(
        action=body.action,
        results=results,
        succeeded=succeeded,
        failed=failed,
        case_id=case_id,
    )

    if bus is not None:
        try:
            await bus.publish(
                {
                    "action": body.action,
                    "count": succeeded,
                    "failed": failed,
                    "case_id": case_id,
                },
                event_type="bulk",
            )
        except Exception:  # pragma: no cover - defensive
            logger.debug("SSE bulk publish failed", exc_info=True)

    record_audit(
        request,
        actor_id=user.id,
        subject_kind="inbox_bulk",
        subject_id=None,
        action=body.action,
        payload={
            "selection_size": len(detection_ids),
            "succeeded": succeeded,
            "failed": failed,
            "case_id": case_id,
        },
    )

    return response


# ---------------------------------------------------------------------------
# /api/inbox/export.csv
# ---------------------------------------------------------------------------


_CSV_HEADER = [
    "id",
    "ingested_at",
    "event_id",
    "function_id",
    "anomaly_type",
    "severity",
    "trust_score",
    "decision",
    "risk_band",
    "mitre_techniques",
]


@router.get("/export.csv")
def inbox_export_csv(
    request: Request,
    severity: Optional[str] = Query(default=None),
    anomaly_type: Optional[str] = Query(default=None),
    function_id: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    mitre_technique: Optional[str] = Query(default=None),
    decision: Optional[str] = Query(default=None),
    risk_band: Optional[str] = Query(default=None),
    text: Optional[str] = Query(default=None),
    case_status: Optional[str] = Query(default=None),
    limit: int = Query(default=10_000, ge=1, le=50_000),
) -> StreamingResponse:
    """Stream the filtered rows as RFC 4180 CSV."""

    store: DetectionStore = request.app.state.store
    filters = _parse_filters(
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
    )
    rows, _ = store.list_detections(**filters, limit=limit, offset=0)

    def _gen():
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(_CSV_HEADER)
        yield buf.getvalue()
        for r in rows:
            buf.seek(0)
            buf.truncate(0)
            writer.writerow(
                [
                    r.id,
                    r.ingested_at.isoformat(),
                    r.event_id,
                    r.function_id,
                    r.anomaly_type,
                    r.severity,
                    f"{r.trust_score:.4f}",
                    r.decision or "",
                    r.risk_band or "",
                    ";".join(r.mitre_techniques),
                ]
            )
            yield buf.getvalue()

    headers = {"Content-Disposition": 'attachment; filename="scafad-inbox.csv"'}
    return StreamingResponse(_gen(), media_type="text/csv; charset=utf-8", headers=headers)


__all__ = ["router"]
