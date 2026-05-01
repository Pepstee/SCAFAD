"""``/api/functions`` routes for Phase 3."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..functions import aggregate_functions, aggregate_function_detail
from ..schemas import FunctionListResponse, FunctionDetail


router = APIRouter(prefix="/api/functions", tags=["functions"])


@router.get("", response_model=FunctionListResponse)
def list_functions(
    request: Request,
    severity: Optional[str] = Query(default=None),
    mitre_technique: Optional[str] = Query(default=None),
    sort: str = Query(default="last_seen_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> FunctionListResponse:
    """List functions aggregated from detections."""
    store = request.app.state.store
    result = aggregate_functions(
        store,
        severity=severity,
        mitre_technique=mitre_technique,
        sort=sort,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return FunctionListResponse(
        items=[
            {
                "function_id": item["function_id"],
                "last_seen": item["last_seen"],
                "count_24h": item["count_24h"],
                "count_7d": item["count_7d"],
                "severity_max": item["severity_max"],
                "open_case_count": item["open_case_count"],
                "top_mitre": item["top_mitre"],
            }
            for item in result["items"]
        ],
        total=result["total"],
        limit=page_size,
        offset=(page - 1) * page_size,
    )


@router.get("/{function_id}", response_model=FunctionDetail)
def get_function_detail(
    request: Request,
    function_id: str,
    window_days: int = Query(default=7, ge=1, le=90),
) -> FunctionDetail:
    """Get detailed aggregates for a single function."""
    store = request.app.state.store

    # Verify function exists
    rows, _ = store.list_detections(function_id=function_id, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail=f"function '{function_id}' not found")

    result = aggregate_function_detail(
        store,
        function_id,
        window_days=window_days,
    )
    return FunctionDetail(**result)


__all__ = ["router"]
