"""Adapter that wraps :class:`SCAFADCanonicalRuntime` for the GUI backend.

The adapter is a *thin*, *read-only* facade.  It never modifies any module
under ``scafad.layer*`` or ``scafad.runtime``.  The only state it owns is the
runtime singleton itself (kept across requests so the L0 historical-data
window accumulates) and a per-process latency record used to compute the
``layer_p95_ms`` KPI.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


logger = logging.getLogger("scafad.gui.runtime_adapter")


@dataclass
class IngestionOutcome:
    """The minimal slice of a runtime result the GUI persists and returns."""

    event_id: str
    function_id: str
    anomaly_type: str
    severity: str
    trust_score: float
    mitre_techniques: List[str]
    decision: Optional[str]
    risk_band: Optional[str]
    duration_ms: float
    layer_payload: Dict[str, Any]
    correlation_id: Optional[str] = None


@dataclass
class _LatencyRing:
    """Bounded ring buffer of recent runtime latencies (ms) for percentile reporting."""

    capacity: int = 256
    samples: List[float] = field(default_factory=list)

    def push(self, value_ms: float) -> None:
        self.samples.append(float(value_ms))
        if len(self.samples) > self.capacity:
            del self.samples[: len(self.samples) - self.capacity]

    def p95(self) -> float:
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        idx = int(round(0.95 * (len(ordered) - 1)))
        return float(ordered[idx])

    def p50(self) -> float:
        """Return the 50th-percentile (median) latency, or 0.0 if empty."""
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        idx = int(round(0.50 * (len(ordered) - 1)))
        return float(ordered[idx])

    def p99(self) -> float:
        """Return the 99th-percentile latency, or 0.0 if empty."""
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        idx = int(round(0.99 * (len(ordered) - 1)))
        return float(ordered[idx])

    def mean(self) -> float:
        """Return mean latency in ms, or 0.0 if empty."""
        if not self.samples:
            return 0.0
        return sum(self.samples) / len(self.samples)

    def count(self) -> int:
        """Return number of samples recorded."""
        return len(self.samples)


class _PerLayerLatencyRings:
    """One :class:`_LatencyRing` per SCAFAD layer (Phase 4).

    Updated inside :meth:`GUIRuntimeAdapter.ingest` from the
    ``multilayer_result.layer<n>.duration_ms`` fields the runtime returns.
    No persistence — restart resets the rings (ADR-A4-5).
    """

    LAYER_NAMES = ("layer0", "layer1", "layer2", "layer3", "layer4", "layer5", "layer6")

    def __init__(self, capacity: int = 256) -> None:
        self._rings: Dict[str, _LatencyRing] = {
            name: _LatencyRing(capacity=capacity) for name in self.LAYER_NAMES
        }

    def push(self, layer_name: str, value_ms: float) -> None:
        """Record one latency sample for *layer_name*; unknown layers are ignored."""
        ring = self._rings.get(layer_name)
        if ring is not None:
            ring.push(value_ms)

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        """Return ``{layer_name: {p50, p95, p99, mean_ms, count}}`` for all layers."""
        return {
            name: {
                "p50": ring.p50(),
                "p95": ring.p95(),
                "p99": ring.p99(),
                "mean_ms": ring.mean(),
                "count": float(ring.count()),
            }
            for name, ring in self._rings.items()
        }


class GUIRuntimeAdapter:
    """Process-wide adapter around :class:`SCAFADCanonicalRuntime`.

    The adapter is constructed lazily on the first :meth:`ingest` call so that
    importing the FastAPI app does not pay the L0 detector init cost (~1 s in
    practice).  A reentrant lock serialises ingest calls to keep the
    L0 historical buffer monotonic.
    """

    def __init__(self) -> None:
        self._runtime: Any = None
        self._lock = threading.RLock()
        self._latency = _LatencyRing()
        self._per_layer_rings = _PerLayerLatencyRings()
        self._warmed: bool = False

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _ensure_runtime(self) -> Any:
        if self._runtime is not None:
            return self._runtime
        # Imported lazily so that ``scafad.gui.backend`` may be imported
        # in environments where ``scafad/`` is not yet on sys.path.
        from scafad.runtime import SCAFADCanonicalRuntime  # local import

        self._runtime = SCAFADCanonicalRuntime()
        self._warmed = True
        logger.info("SCAFADCanonicalRuntime initialised for GUI backend")
        return self._runtime

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, event: Dict[str, Any]) -> IngestionOutcome:
        """Run the canonical runtime on ``event`` and return a flat outcome.

        The returned object is JSON-serialisable end-to-end; the caller only
        needs to persist :attr:`IngestionOutcome.layer_payload` and the cheap
        scalar fields.
        """

        runtime = self._ensure_runtime()
        with self._lock:
            t0 = time.perf_counter()
            result = runtime.process_event(event)
            duration_ms = (time.perf_counter() - t0) * 1000.0
        self._latency.push(duration_ms)

        payload = result.to_dict()

        # Push per-layer durations into per-layer rings (Phase 4).
        multilayer = payload.get("multilayer_result", {}) or {}
        for i in range(7):
            layer_key = f"layer{i}"
            layer_data = multilayer.get(layer_key, {})
            if isinstance(layer_data, dict):
                layer_dur = layer_data.get("duration_ms", 0.0)
                if layer_dur:
                    self._per_layer_rings.push(layer_key, float(layer_dur))

        return self._project_outcome(payload, duration_ms=duration_ms, event=event)

    def latency_p95_ms(self) -> float:
        """Return the rolling p95 latency observed by this adapter."""

        return self._latency.p95()

    def reset_latency(self) -> None:
        """Reset the latency ring; primarily used by tests."""

        self._latency = _LatencyRing()

    # ------------------------------------------------------------------
    # Phase 4 — per-layer latency + config snapshot
    # ------------------------------------------------------------------

    def is_warmed(self) -> bool:
        """Return ``True`` after the first successful :meth:`ingest` call."""
        return self._warmed

    def latency_per_layer(self) -> Dict[str, Dict[str, float]]:
        """Return ``{layer_name: {p50, p95, p99, mean_ms, count}}`` per layer.

        All values are ``0.0`` / ``0`` until the runtime is warmed and has
        processed events.
        """
        return self._per_layer_rings.snapshot()

    def snapshot_config(self) -> Dict[str, Any]:
        """Return a read-only snapshot of the runtime's detector configuration.

        Returns ``{"available": False, ...}`` if the runtime is not yet warmed.
        No new imports of ``scafad.layer*`` are made; the adapter introspects
        the runtime singleton it already owns (ADR-A4-7).
        """
        if not self._warmed or self._runtime is None:
            return {
                "available": False,
                "detector_panel": {"available": False, "detectors": []},
                "fusion": {"layer_weights": {}, "risk_band_thresholds": {}},
            }
        try:
            detectors = []
            # Try common attribute names for the L0 detection engine.
            engine = (
                getattr(self._runtime, "engine", None)
                or getattr(self._runtime, "_engine", None)
            )
            if engine is not None:
                detector_map = (
                    getattr(engine, "detectors", None)
                    or getattr(engine, "_detectors", None)
                    or {}
                )
                for det_id, det in detector_map.items():
                    detectors.append({
                        "id": str(det_id),
                        "weight": float(getattr(det, "weight", 1.0)),
                        "threshold": (
                            float(getattr(det, "threshold", 0.0))
                            if hasattr(det, "threshold") else None
                        ),
                        "last_signal_at": None,
                    })
            fusion_weights: Dict[str, float] = {}
            risk_thresholds: Dict[str, float] = {}
            fusion = (
                getattr(self._runtime, "fusion", None)
                or getattr(self._runtime, "_fusion", None)
            )
            if fusion is not None:
                fusion_weights = {
                    str(k): float(v)
                    for k, v in getattr(fusion, "layer_weights", {}).items()
                }
                risk_thresholds = {
                    str(k): float(v)
                    for k, v in getattr(fusion, "risk_band_thresholds", {}).items()
                }
            return {
                "available": True,
                "detector_panel": {
                    "available": bool(detectors),
                    "detectors": detectors,
                },
                "fusion": {
                    "layer_weights": fusion_weights,
                    "risk_band_thresholds": risk_thresholds,
                },
            }
        except Exception as exc:  # pragma: no cover
            logger.warning("snapshot_config failed: %s", exc)
            return {
                "available": False,
                "detector_panel": {"available": False, "detectors": []},
                "fusion": {"layer_weights": {}, "risk_band_thresholds": {}},
            }

    # ------------------------------------------------------------------
    # Projection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _project_outcome(
        payload: Dict[str, Any], *, duration_ms: float, event: Dict[str, Any]
    ) -> IngestionOutcome:
        layer0 = payload.get("layer0_record", {}) or {}
        layer1 = payload.get("layer1_record", {}) or {}
        multilayer = payload.get("multilayer_result", {}) or {}
        layer3 = multilayer.get("layer3", {}) or {}
        layer4 = multilayer.get("layer4", {}) or {}
        layer5 = multilayer.get("layer5", {}) or {}

        severity = str(layer4.get("decision") or "observe").lower()
        if severity not in {"observe", "review", "escalate"}:
            severity = "observe"

        anomaly_type = str(
            layer1.get("anomaly_type")
            or layer0.get("anomaly_type")
            or event.get("anomaly_type")
            or event.get("anomaly")
            or "benign"
        )

        techniques_raw = layer5.get("techniques") or []
        if isinstance(techniques_raw, dict):  # defensive
            techniques: List[str] = list(techniques_raw.keys())
        else:
            techniques = [str(t) for t in techniques_raw]

        trust_score = float(layer3.get("fused_score") or 0.0)
        risk_band = layer3.get("risk_band")
        decision = layer4.get("decision")

        return IngestionOutcome(
            event_id=str(layer0.get("event_id") or event.get("event_id") or ""),
            function_id=str(
                layer0.get("function_id")
                or event.get("function_id")
                or event.get("function_name")
                or "unknown_function"
            ),
            anomaly_type=anomaly_type,
            severity=severity,
            trust_score=trust_score,
            mitre_techniques=techniques,
            decision=str(decision) if decision is not None else None,
            risk_band=str(risk_band) if risk_band is not None else None,
            duration_ms=float(duration_ms),
            layer_payload=payload,
            correlation_id=str(layer1.get("trace_id") or layer1.get("record_id") or ""),
        )


__all__ = ["GUIRuntimeAdapter", "IngestionOutcome", "_LatencyRing", "_PerLayerLatencyRings"]
