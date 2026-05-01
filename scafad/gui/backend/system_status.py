"""System health and metrics composer for SCAFAD GUI (Phase 4).

Phase 4 extends the static system/status endpoint with live per-layer latency
metrics from the in-process :class:`~.runtime_adapter.GUIRuntimeAdapter` rings,
plus aggregate telemetry pulled from the detection store.

All logic here is read-only — no DB writes, no imports of ``scafad.layer*``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .schemas import (
    DetectorEntry,
    DetectorPanel,
    LayerStatusExtended,
    MetricsTimeseriesResponse,
    SystemMetricsResponse,
    TimeseriesPoint,
)

logger = logging.getLogger("scafad.gui.system_status")

# ---------------------------------------------------------------------------
# Static layer metadata (description, default detector count)
# ---------------------------------------------------------------------------

_LAYER_META: List[tuple] = [
    ("layer0", "Anomaly Detection (L0)", 26),
    ("layer1", "Hashing Pipeline (L1)", 0),
    ("layer2", "Semantic Analyser (L2)", 0),
    ("layer3", "Fusion Engine (L3)", 0),
    ("layer4", "Decision Engine (L4)", 0),
    ("layer5", "Threat Intelligence (L5)", 0),
    ("layer6", "Orchestrator (L6)", 0),
]

_WINDOW_DELTA: Dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

_BIN_DELTA: Dict[str, timedelta] = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "1d": timedelta(days=1),
}


def _parse_window(window: str) -> timedelta:
    return _WINDOW_DELTA.get(window, timedelta(hours=24))


def _parse_bin(bin_spec: str) -> timedelta:
    return _BIN_DELTA.get(bin_spec, timedelta(hours=1))


# ---------------------------------------------------------------------------
# Public composers
# ---------------------------------------------------------------------------


def compose_system_metrics(
    *,
    store: Any,
    adapter: Any,
) -> SystemMetricsResponse:
    """Compose a :class:`SystemMetricsResponse` from live adapter + store data.

    Parameters
    ----------
    store:
        The :class:`~.store.DetectionStore` instance (duck-typed).
    adapter:
        The :class:`~.runtime_adapter.GUIRuntimeAdapter` instance (duck-typed).
    """
    latency_data: Dict[str, Dict[str, float]] = adapter.latency_per_layer()
    config_data: Dict[str, Any] = adapter.snapshot_config()
    warmed: bool = adapter.is_warmed()

    # Derive detector count: prefer live panel; fall back to static meta.
    panel_detectors = config_data.get("detector_panel", {}).get("detectors", [])
    detector_count: int = len(panel_detectors) if panel_detectors else 26

    layers: List[LayerStatusExtended] = []
    for name, description, static_det_count in _LAYER_META:
        ring = latency_data.get(name, {})
        layers.append(
            LayerStatusExtended(
                layer=name,
                healthy=True,
                description=description,
                detector_count=static_det_count,
                p50_ms=round(ring.get("p50", 0.0), 3),
                p95_ms=round(ring.get("p95", 0.0), 3),
                p99_ms=round(ring.get("p99", 0.0), 3),
                error_rate_pct=0.0,
                recent_count=int(ring.get("count", 0.0)),
            )
        )

    db_size: int = store.db_size_bytes()
    last_ingest: Optional[datetime] = store.last_ingest_at()
    total: int = store.total_count()
    audit_total: int = store.count_audit_events()

    return SystemMetricsResponse(
        layers=layers,
        detector_count=detector_count,
        db_size_bytes=db_size,
        last_ingest_at=last_ingest,
        detections_total=total,
        audit_events_total=audit_total,
        runtime_warmed=warmed,
    )


def compose_detector_panel(*, adapter: Any) -> DetectorPanel:
    """Return the live detector panel from the runtime snapshot.

    Returns ``DetectorPanel(available=False, detectors=[])`` when the
    runtime is not yet warmed (ADR-A4-7).
    """
    config: Dict[str, Any] = adapter.snapshot_config()
    if not config.get("available", False):
        return DetectorPanel(available=False, detectors=[])

    panel = config.get("detector_panel", {})
    detectors = [
        DetectorEntry(
            id=d["id"],
            weight=d.get("weight", 1.0),
            threshold=d.get("threshold"),
            last_signal_at=None,
        )
        for d in panel.get("detectors", [])
    ]
    return DetectorPanel(available=bool(detectors), detectors=detectors)


def compose_metrics_timeseries(
    *,
    window: str = "24h",
    bin_spec: str = "1h",
) -> MetricsTimeseriesResponse:
    """Return a continuous, gap-free timeseries of latency bins.

    Phase 4 uses in-memory rings (not persisted), so all historical bins
    contain zeros.  The bins are generated from *now* backwards so the
    frontend always receives a gap-free series matching the requested window.
    Phase 5 will persist per-bin metrics.
    """
    window_td = _parse_window(window)
    bin_td = _parse_bin(bin_spec)

    now = datetime.now(timezone.utc)
    start = now - window_td

    num_bins = max(1, int(window_td / bin_td))
    bin_starts = [start + bin_td * i for i in range(num_bins)]

    series: Dict[str, List[TimeseriesPoint]] = {}
    for name, _, _ in _LAYER_META:
        series[name] = [
            TimeseriesPoint(ts=bs, p50_ms=0.0, p95_ms=0.0, error_rate_pct=0.0, count=0)
            for bs in bin_starts
        ]

    return MetricsTimeseriesResponse(
        window_spec=window,
        bin=bin_spec,
        series=series,
    )


__all__ = [
    "compose_system_metrics",
    "compose_detector_panel",
    "compose_metrics_timeseries",
]
