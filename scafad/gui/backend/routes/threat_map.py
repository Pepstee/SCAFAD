"""``/api/threat-map`` routes for Phase 3."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..schemas import ThreatMapResponse, ThreatMapGridResponse
from ..threat_map import aggregate_threat_map, MITRE_TACTIC_TECHNIQUE_GRID, TECHNIQUE_TO_TACTIC
from ..time_window import parse_window
from ..store import _iso


router = APIRouter(prefix="/api/threat-map", tags=["threat-map"])


@router.get("", response_model=ThreatMapResponse)
def get_threat_map(
    request: Request,
    window: str = Query(default="7d"),
    custom_since: Optional[datetime] = Query(default=None),
    custom_until: Optional[datetime] = Query(default=None),
) -> ThreatMapResponse:
    """Get the threat-map matrix for a time window."""
    store = request.app.state.store

    try:
        since, until = parse_window(window, custom_since=custom_since, custom_until=custom_until)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    matrix = aggregate_threat_map(store, since=since, until=until)
    return ThreatMapResponse(
        matrix=matrix,
        window_spec=window,
        since=_iso(since),
        until=_iso(until),
    )


@router.get("/grid", response_model=ThreatMapGridResponse)
def get_threat_map_grid(request: Request) -> ThreatMapGridResponse:
    """Get the static MITRE tactic/technique vocabulary."""
    return ThreatMapGridResponse(
        tactics={
            tactic: [{"id": t.id, "name": t.name, "description": t.description}
                    for t in techniques]
            for tactic, techniques in MITRE_TACTIC_TECHNIQUE_GRID.items()
        }
    )


@router.get("/cells/{technique_id}/detections", response_model=dict)
def get_cell_detections(
    request: Request,
    technique_id: str,
    window: str = Query(default="7d"),
    custom_since: Optional[datetime] = Query(default=None),
    custom_until: Optional[datetime] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> dict:
    """Get detections that hit a specific MITRE technique cell."""
    store = request.app.state.store

    # Validate technique_id
    if technique_id not in TECHNIQUE_TO_TACTIC:
        raise HTTPException(status_code=404, detail=f"technique '{technique_id}' not found")

    try:
        since, until = parse_window(window, custom_since=custom_since, custom_until=custom_until)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # List detections matching the technique
    rows, total = store.list_detections(
        mitre_technique=technique_id,
        since=since,
        until=until,
        limit=page_size,
        offset=(page - 1) * page_size,
    )

    from ..store import detection_to_summary_dict
    from ..schemas import DetectionSummary
    items = [DetectionSummary(**detection_to_summary_dict(r)) for r in rows]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "technique_id": technique_id,
        "tactic": TECHNIQUE_TO_TACTIC.get(technique_id),
    }


__all__ = ["router"]
