"""Function-level aggregation for Phase 3 Functions page.

This module provides utility functions to call the DetectionStore and shape
the responses for the HTTP API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .store import DetectionStore
from .time_window import parse_window, default_bins_for_window, bin_duration_seconds


def aggregate_functions(
    store: DetectionStore,
    *,
    severity: Optional[str] = None,
    mitre_technique: Optional[str] = None,
    sort: str = "last_seen_desc",
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Aggregate functions (one row per distinct function_id).

    Args:
        store: The DetectionStore instance.
        severity: Optional severity filter ("observe", "review", "escalate").
        mitre_technique: Optional technique filter (e.g. "T1059").
        sort: Sort order (last_seen_desc, count_24h_desc, count_7d_desc, open_case_count_desc).
        limit: Result limit.
        offset: Result offset.

    Returns:
        Dict with "items" (list of function dicts), "total", "limit", "offset".
    """
    rows, total = store.function_rollup(
        severity=severity,
        mitre_technique=mitre_technique,
        sort=sort,
        limit=limit,
        offset=offset,
    )

    items = []
    for row in rows:
        top_mitre = row.get("top_mitre_techniques", [])[:3]
        items.append({
            "function_id": row["function_id"],
            "last_seen": row["last_seen"],
            "count_24h": row["count_24h"],
            "count_7d": row["count_7d"],
            "severity_max": row["severity_max"],
            "open_case_count": row["open_case_count"],
            "top_mitre": top_mitre,
        })

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def aggregate_function_detail(
    store: DetectionStore,
    function_id: str,
    *,
    window_days: int = 7,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Fetch detailed aggregates for a single function.

    Args:
        store: The DetectionStore instance.
        function_id: The function ID to fetch details for.
        window_days: If since/until not provided, use this many days.
        since: Optional explicit start time.
        until: Optional explicit end time.

    Returns:
        Dict with sparkline, severity_mix, top_mitre, recent_detections, linked_cases.
    """
    # Resolve window
    if since is None or until is None:
        now = datetime.utcnow().replace(microsecond=0)
        since = now - __import__("datetime").timedelta(days=window_days)
        until = now
    else:
        until = until or datetime.utcnow().replace(microsecond=0)
        since = since or (until - __import__("datetime").timedelta(days=window_days))

    detail_rows = store.function_detail_rows(function_id, since=since, until=until)

    # Build sparkline
    bin_spec = default_bins_for_window(int((until - since).total_seconds()))
    histogram = store.histogram_for_function(
        function_id,
        since=since,
        until=until,
        bin=bin_spec,
    )
    sparkline = [
        {
            "bucket_start": bin["bucket_start"],
            "count": bin["count"],
            "severity_max": bin.get("severity_max"),
        }
        for bin in histogram
    ]

    return {
        "function_id": function_id,
        "severity_counts": detail_rows["severity_counts"],
        "mitre_counts": detail_rows["mitre_counts"],
        "top_mitre": [
            {"id": tid, "count": count}
            for tid, count in sorted(
                detail_rows["mitre_counts"].items(),
                key=lambda x: -x[1],
            )[:5]
        ],
        "sparkline": sparkline,
        "recent_detections": [
            {
                "id": d["id"],
                "ingested_at": d["ingested_at"],
                "severity": d["severity"],
                "anomaly_type": d["anomaly_type"],
                "mitre_techniques": d.get("mitre_techniques", []),
            }
            for d in detail_rows["recent_detections"]
        ],
        "linked_cases": [
            {
                "case_id": c["id"],
                "title": c["title"],
                "status": c["status"],
                "severity_rollup": c["severity_rollup"],
            }
            for c in detail_rows["linked_cases"]
        ],
    }


__all__ = [
    "aggregate_functions",
    "aggregate_function_detail",
]
