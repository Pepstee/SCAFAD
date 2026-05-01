"""Audit log routes for SCAFAD GUI (Phase 4).

Endpoints
---------
GET /api/audit                   paginated, filtered list of audit events
GET /api/audit/verify            recompute hash chain, return ok/broken
GET /api/audit/export.csv        streaming CSV export
GET /api/audit/export.json       streaming NDJSON export
GET /api/audit/subjects          distinct actors / subject_kinds / actions
GET /api/audit/{id}              single audit event by id

**Path ordering matters:** ``/verify``, ``/export.csv``, ``/export.json``,
and ``/subjects`` MUST be declared BEFORE ``/{id}`` to prevent the
parameterised route capturing the literal path segments.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ..schemas import AuditChainVerification, AuditEvent, AuditEventListResponse
from ..store import AuditEventRow

logger = logging.getLogger("scafad.gui.routes.audit")

router = APIRouter(prefix="/api/audit", tags=["audit"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dto(row: AuditEventRow) -> AuditEvent:
    return AuditEvent(
        id=row.id,
        ts=row.ts,
        actor_id=row.actor_id,
        subject_kind=row.subject_kind,  # type: ignore[arg-type]
        subject_id=row.subject_id,
        action=row.action,
        payload=row.payload,
        prev_hash=row.prev_hash,
        row_hash=row.row_hash,
    )


# ---------------------------------------------------------------------------
# Non-parameterised routes (MUST come before /{id})
# ---------------------------------------------------------------------------


@router.get("/verify", response_model=AuditChainVerification)
def verify_audit_chain(request: Request) -> AuditChainVerification:
    """Recompute the full SHA-256 hash chain and return the integrity result."""
    store = request.app.state.store
    result = store.verify_audit_chain()
    return AuditChainVerification(
        ok=result.ok,
        last_verified_id=result.last_verified_id,
        broken_at=result.broken_at,
        total_rows=result.total_rows,
    )


@router.get("/export.csv")
def export_audit_csv(
    request: Request,
    actor: Optional[str] = Query(default=None),
    subject_kind: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
) -> StreamingResponse:
    """Stream matching audit rows as CSV (RFC 4180).

    Downloads as ``audit_export.csv``.
    """
    store = request.app.state.store

    def _generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "id", "ts", "actor_id", "subject_kind", "subject_id",
            "action", "prev_hash", "row_hash",
        ])
        yield buf.getvalue()

        offset = 0
        page_size = 500
        while True:
            rows, _ = store.list_audit_events(
                actor_id=actor,
                subject_kind=subject_kind,
                action=action,
                since=since,
                until=until,
                limit=page_size,
                offset=offset,
            )
            if not rows:
                break
            for row in rows:
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow([
                    row.id,
                    row.ts.isoformat(),
                    row.actor_id,
                    row.subject_kind,
                    row.subject_id or "",
                    row.action,
                    row.prev_hash,
                    row.row_hash,
                ])
                yield buf.getvalue()
            if len(rows) < page_size:
                break
            offset += page_size

    return StreamingResponse(
        _generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
    )


@router.get("/export.json")
def export_audit_json(
    request: Request,
    actor: Optional[str] = Query(default=None),
    subject_kind: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
) -> StreamingResponse:
    """Stream matching audit rows as NDJSON (one JSON object per line).

    Downloads as ``audit_export.jsonl``.
    """
    store = request.app.state.store

    def _generate():
        offset = 0
        page_size = 500
        while True:
            rows, _ = store.list_audit_events(
                actor_id=actor,
                subject_kind=subject_kind,
                action=action,
                since=since,
                until=until,
                limit=page_size,
                offset=offset,
            )
            if not rows:
                break
            for row in rows:
                obj = {
                    "id": row.id,
                    "ts": row.ts.isoformat(),
                    "actor_id": row.actor_id,
                    "subject_kind": row.subject_kind,
                    "subject_id": row.subject_id,
                    "action": row.action,
                    "payload": row.payload,
                    "prev_hash": row.prev_hash,
                    "row_hash": row.row_hash,
                }
                yield json.dumps(obj, ensure_ascii=False) + "\n"
            if len(rows) < page_size:
                break
            offset += page_size

    return StreamingResponse(
        _generate(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=audit_export.jsonl"},
    )


@router.get("/subjects")
def list_audit_subjects(request: Request) -> dict:
    """Return distinct subject_kinds, actions, and actors for filter-bar population."""
    store = request.app.state.store
    actors = store.list_audit_distinct_actors()
    return {
        "subject_kinds": [
            "detection", "case", "view", "inbox_bulk", "ingest", "system", "comment",
        ],
        "actions": [
            "created", "updated", "deleted", "attached", "detached",
            "exported", "viewed", "assigned", "dismissed",
        ],
        "actors": actors,
    }


# ---------------------------------------------------------------------------
# Parameterised routes (MUST come after the literal routes above)
# ---------------------------------------------------------------------------


@router.get("", response_model=AuditEventListResponse)
def list_audit_events(
    request: Request,
    actor: Optional[str] = Query(default=None, description="Filter by actor_id"),
    subject_kind: Optional[str] = Query(default=None, description="Filter by subject_kind"),
    action: Optional[str] = Query(default=None, description="Filter by action"),
    since: Optional[datetime] = Query(default=None, description="Inclusive lower bound (ISO-8601)"),
    until: Optional[datetime] = Query(default=None, description="Inclusive upper bound (ISO-8601)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> AuditEventListResponse:
    """Paginated, filtered list of audit events (newest first)."""
    store = request.app.state.store
    offset = (page - 1) * page_size
    rows, total = store.list_audit_events(
        actor_id=actor,
        subject_kind=subject_kind,
        action=action,
        since=since,
        until=until,
        limit=page_size,
        offset=offset,
    )
    return AuditEventListResponse(
        items=[_row_to_dto(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{event_id}", response_model=AuditEvent)
def get_audit_event(event_id: str, request: Request) -> AuditEvent:
    """Retrieve a single audit event by id (404 if not found)."""
    store = request.app.state.store
    row = store.get_audit_event(event_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Audit event {event_id!r} not found",
        )
    return _row_to_dto(row)
