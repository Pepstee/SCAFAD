"""System status and metrics routes for SCAFAD GUI (Phase 4).

Moves ``GET /api/system/status`` here from ``routes/health.py`` (ADR-A4-1) and
adds three new endpoints:

* ``GET /api/system/metrics`` — full aggregate snapshot
* ``GET /api/system/metrics/timeseries`` — per-layer latency bins
* ``GET /api/system/detectors`` — live detector panel

The URL ``/api/system/status`` is preserved unchanged; only the implementing
module moves.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ..schemas import (
    DetectorPanel,
    MetricsTimeseriesResponse,
    SystemMetricsResponse,
)
from ..system_status import (
    compose_detector_panel,
    compose_metrics_timeseries,
    compose_system_metrics,
)

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status", response_model=SystemMetricsResponse)
def get_system_status(request: Request) -> SystemMetricsResponse:
    """Extended system status — per-layer latency p50/p95/p99 + aggregate metrics.

    Replaces the static Phase-1 endpoint.  URL ``/api/system/status`` is
    unchanged; the schema is additive (all Phase-1 fields are present).
    """
    store = request.app.state.store
    adapter = request.app.state.runtime_adapter
    return compose_system_metrics(store=store, adapter=adapter)


@router.get("/metrics", response_model=SystemMetricsResponse)
def get_system_metrics(request: Request) -> SystemMetricsResponse:
    """System-wide aggregate metrics snapshot (same payload as ``/status``)."""
    store = request.app.state.store
    adapter = request.app.state.runtime_adapter
    return compose_system_metrics(store=store, adapter=adapter)


@router.get("/metrics/timeseries", response_model=MetricsTimeseriesResponse)
def get_metrics_timeseries(
    request: Request,
    window: str = Query(default="24h", description="Time window: 1h|6h|12h|24h|7d|30d"),
    bin: str = Query(default="1h", description="Bin size: 5m|15m|1h|6h|1d"),
) -> MetricsTimeseriesResponse:
    """Per-layer latency timeseries.

    Phase 4: bins are pre-generated with zeros for historical data since latency
    rings are in-memory only.  Phase 5 will persist per-bin metrics to SQLite.
    """
    return compose_metrics_timeseries(window=window, bin_spec=bin)


@router.get("/detectors", response_model=DetectorPanel)
def get_detectors(request: Request) -> DetectorPanel:
    """Live detector panel.

    Returns ``{available: false, detectors: []}`` if the runtime has not yet
    been warmed by a first ingest (ADR-A4-7).
    """
    adapter = request.app.state.runtime_adapter
    return compose_detector_panel(adapter=adapter)
