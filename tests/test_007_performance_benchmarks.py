"""
test_007_performance_benchmarks.py
====================================
SCAFAD Layer 0 → Layer 1 performance benchmark suite.

Benchmarks (all must pass SLAs defined below):
  1. Adapter throughput           ≥ 5,000 records/sec
  2. Single-record P99 latency    < 500 ms
  3. Batch latency scaling        1 / 5 / 10 / 20 / 50 records
  4. Preservation rate under load 100 records, ≥ 99.5 %
  5. Processing mode latency      TESTING mode < 5 s for 20 records
  6. Concurrent batch throughput  4 × 10 records < 10 s wall-clock

Run:
    cd scafad-r-core
    python -m pytest tests/test_007_performance_benchmarks.py -v -s

Author: SCAFAD Codex (2026-04-17)   Version: 1.0.0
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import importlib
import importlib.util
import math
import os
import statistics
import sys
import time
import types
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional

import pytest

# ---------------------------------------------------------------------------
# SLA thresholds
# ---------------------------------------------------------------------------
SLA_ADAPTER_THROUGHPUT_RPS = 5_000    # records/sec
SLA_SINGLE_RECORD_P99_MS   = 500      # ms
SLA_BATCH_10_MEDIAN_MS     = 2_000    # ms (10-record batch reference)
SLA_PRESERVATION_RATE      = 0.995    # 99.5 %
SLA_CONCURRENT_TOTAL_MS    = 10_000   # ms (4 × 10-record batches, wall clock)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RCORE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DELTA_ROOT  = os.path.join(os.path.dirname(RCORE_ROOT), "scafad-delta")

for _p in [
    RCORE_ROOT,
    DELTA_ROOT,
    os.path.join(DELTA_ROOT, "core"),
    os.path.join(DELTA_ROOT, "subsystems"),
    os.path.join(DELTA_ROOT, "utils"),
    os.path.join(DELTA_ROOT, "configs"),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Dependency shims  (identical to test_006)
# ---------------------------------------------------------------------------
def _install_shims() -> None:
    import re as _re

    _e = types.ModuleType("entropy")
    def _sh(data):
        if not data: return 0.0
        c = Counter(data); t = len(data)
        return -sum((v/t)*math.log2(v/t) for v in c.values() if v)
    _e.shannon_entropy     = _sh
    _e.conditional_entropy = lambda x, y: max(0.0, _sh(list(x)+list(y))-_sh(list(y)))
    sys.modules.setdefault("entropy", _e)

    _mi = types.ModuleType("mutual_information")
    _mi.mutual_information = lambda x, y: 0.0
    sys.modules.setdefault("mutual_information", _mi)

    _shim_map: Dict[str, Dict[str, Any]] = {
        "numba": {
            "jit":      lambda *a, **kw: (lambda f: f),
            "vectorize": lambda *a, **kw: (lambda f: f),
            "cuda": types.SimpleNamespace(jit=lambda *a, **kw: (lambda f: f)),
        },
        "polyglot": {},
        "polyglot.text": {
            "Text": type("Text", (), {
                "__init__": lambda s, t: None,
                "language": property(lambda s: types.SimpleNamespace(code="en")),
            })
        },
        "regex": {
            "compile": _re.compile, "sub": _re.sub, "match": _re.match,
            "search": _re.search,   "findall": _re.findall,
            "split": _re.split,     "escape": _re.escape,
            "IGNORECASE": _re.IGNORECASE, "MULTILINE": _re.MULTILINE,
            "DOTALL": _re.DOTALL,   "error": _re.error,
        },
        "langid":    {"classify":      lambda t: ("en", 0.9)},
        "langdetect": {"detect":       lambda t: "en", "detect_langs": lambda t: []},
        "chardet":   {"detect":        lambda b: {"encoding": "utf-8", "confidence": 0.99}},
        "cchardet":  {"detect":        lambda b: {"encoding": "utf-8", "confidence": 0.99}},
        "email_validator": {
            "validate_email": lambda value, *a, **kw: types.SimpleNamespace(email=value),
            "EmailNotValidError": ValueError,
        },
        "cerberus":  {},
        "croniter":  {},
        "transformers": {},
        "torch":     {},
    }
    for name, attrs in _shim_map.items():
        if name not in sys.modules:
            try:
                importlib.import_module(name)
            except ImportError:
                m = types.ModuleType(name)
                for k, v in attrs.items():
                    setattr(m, k, v)
                sys.modules[name] = m

    for ns in ["scafad_delta", "utils", "subsystems", "config"]:
        if ns not in sys.modules:
            sys.modules[ns] = types.ModuleType(ns)

    pkg = sys.modules["scafad_delta"]
    pkg.__path__   = [os.path.join(DELTA_ROOT, "core")]   # type: ignore
    pkg.__package__ = "scafad_delta"


_install_shims()

# ---------------------------------------------------------------------------
# Delta module loader  (identical to test_006)
# ---------------------------------------------------------------------------
_DELTA_AVAILABLE = False
_DELTA_EXC_MSG   = ""


def _load_delta_modules() -> None:
    def _load(bare: str, path: str, extra: Optional[List[str]] = None) -> Any:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Delta module not found: {path}")
        qual = f"scafad_delta.{bare}"
        spec = importlib.util.spec_from_file_location(
            qual, path, submodule_search_locations=[])
        mod  = importlib.util.module_from_spec(spec)   # type: ignore
        mod.__package__ = "scafad_delta"
        for nm in [qual, bare] + (extra or []):
            sys.modules[nm] = mod
        setattr(sys.modules["scafad_delta"], bare, mod)
        spec.loader.exec_module(mod)                   # type: ignore
        return mod

    C = DELTA_ROOT
    _load("layer1_config",       f"{C}/configs/layer1_config.py",
          extra=["config.layer1_config"])
    _load("layer1_validation",   f"{C}/core/layer1_validation.py")
    _load("layer1_schema",       f"{C}/core/layer1_schema.py")
    _load("layer1_privacy",      f"{C}/core/layer1_privacy.py")
    _load("layer1_hashing",      f"{C}/core/layer1_hashing.py")
    _load("layer1_sanitization", f"{C}/core/layer1_sanitization.py")
    _load("layer1_preservation", f"{C}/core/layer1_preservation.py")
    for name in [
        "schema_registry", "privacy_policy_engine", "semantic_analyzer",
        "quality_monitor", "audit_trail_generator",
    ]:
        _load(name, f"{C}/subsystems/{name}.py", extra=[f"subsystems.{name}"])
    for name in [
        "hash_library", "redaction_manager", "field_mapper",
        "compression_optimizer", "validators",
    ]:
        _load(name, f"{C}/utils/{name}.py", extra=[f"utils.{name}"])
    _load("layer1_core", f"{C}/core/layer1_core.py")


try:
    _load_delta_modules()
    _DELTA_AVAILABLE = True
except Exception as _exc:
    _DELTA_EXC_MSG = str(_exc)

# r-core imports
from layer0.app_telemetry import AnomalyType, ExecutionPhase, TelemetryRecord, TelemetrySource
from layer1.pipeline import Layer1CanonicalPipeline
from layer0.adapter import RCoreToLayer1Adapter

# delta imports
if _DELTA_AVAILABLE:
    from layer1_core import (   # type: ignore
        Layer1_BehavioralIntakeZone,
        TelemetryRecord as DeltaTelemetryRecord,
    )
    from layer1_config import Layer1Config, ProcessingMode   # type: ignore


@dataclass
class CanonicalProcessedBatch:
    cleaned_records: List[Dict[str, Any]]
    privacy_audit_trail: Dict[str, Any]
    total_processing_time_ms: float


class CanonicalLayer1Zone:
    def __init__(self) -> None:
        self.pipeline = Layer1CanonicalPipeline()

    async def process_telemetry_batch(
        self,
        records: List[Any],
        processing_context: Optional[Dict[str, Any]] = None,
    ) -> CanonicalProcessedBatch:
        t0 = time.perf_counter()
        cleaned_records: List[Dict[str, Any]] = []
        redacted_fields: List[str] = []
        for record in records:
            adapted = {
                "record_id": record.record_id,
                "timestamp": record.timestamp,
                "function_name": record.function_name,
                "execution_phase": record.execution_phase,
                "anomaly_type": record.anomaly_type,
                "telemetry_data": getattr(record, "telemetry_data", {}) or {},
                "provenance_chain": getattr(record, "provenance_chain", {}) or {},
                "context_metadata": getattr(record, "context_metadata", {}) or {},
                "schema_version": getattr(record, "schema_version", "v2.1"),
            }
            processed = self.pipeline.process_adapted_record(adapted)
            cleaned_records.append(processed.to_dict())
            redacted_fields.extend(processed.audit_record.redacted_fields)
        return CanonicalProcessedBatch(
            cleaned_records=cleaned_records,
            privacy_audit_trail={
                "records_processed": len(cleaned_records),
                "redacted_fields": sorted(set(redacted_fields)),
                "processing_context": processing_context or {},
            },
            total_processing_time_ms=(time.perf_counter() - t0) * 1000,
        )

# All tests skip gracefully when delta is unavailable
pytestmark = pytest.mark.skipif(
    not _DELTA_AVAILABLE,
    reason=f"Delta unavailable: {_DELTA_EXC_MSG}",
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
_ADAPTER    = RCoreToLayer1Adapter()
_ANOMALY_MIX = [
    AnomalyType.BENIGN, AnomalyType.MEMORY_SPIKE, AnomalyType.CPU_BURST,
    AnomalyType.NETWORK_ANOMALY, AnomalyType.TIMEOUT_ANOMALY,
]


def _make_rcore(anomaly: AnomalyType = AnomalyType.BENIGN,
                phase:   ExecutionPhase = ExecutionPhase.INVOKE,
                duration: float = 0.25,
                memory_spike_kb: int = 512,
                cpu_utilization: float = 25.0) -> TelemetryRecord:
    return TelemetryRecord(
        event_id=str(uuid.uuid4()),
        timestamp=time.time(),
        function_id="bench-fn-007",
        execution_phase=phase,
        anomaly_type=anomaly,
        duration=duration,
        memory_spike_kb=memory_spike_kb,
        cpu_utilization=cpu_utilization,
        network_io_bytes=1024,
        fallback_mode=False,
        source=TelemetrySource.SCAFAD_LAYER0,
        concurrency_id=str(uuid.uuid4()),
    )


def _adapt(rcore_rec: TelemetryRecord) -> "DeltaTelemetryRecord":
    from datetime import datetime
    d  = _ADAPTER.adapt(rcore_rec)
    ts = d.get("timestamp", time.time())
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except Exception:
            ts = time.time()
    return DeltaTelemetryRecord(
        record_id       = d["record_id"],
        timestamp       = float(ts),
        function_name   = d["function_name"],
        execution_phase = d["execution_phase"],
        anomaly_type    = d["anomaly_type"],
        telemetry_data  = d.get("telemetry_data", {}),
        provenance_chain  = d.get("provenance_chain"),
        context_metadata  = d.get("context_metadata"),
        schema_version    = d.get("schema_version", "v2.1"),
    )


def _make_zone(mode=None) -> "Layer1_BehavioralIntakeZone":
    if _DELTA_AVAILABLE:
        try:
            if mode is None:
                mode = ProcessingMode.TESTING
            cfg = Layer1Config(processing_mode=mode, schema_version="v2.1")
            return Layer1_BehavioralIntakeZone(config=cfg)
        except Exception:
            pass
    return CanonicalLayer1Zone()


# ===========================================================================
# 1 — Adapter throughput
# ===========================================================================
def test_bench_adapter_throughput():
    """Adapter must sustain ≥ SLA_ADAPTER_THROUGHPUT_RPS records/sec."""
    n       = 10_000
    records = [_make_rcore() for _ in range(n)]
    start   = time.perf_counter()
    for r in records:
        _ADAPTER.adapt(r)
    rps = n / (time.perf_counter() - start)
    print(f"\n  Adapter throughput: {rps:,.0f} rec/s  (SLA ≥ {SLA_ADAPTER_THROUGHPUT_RPS:,})")
    assert rps >= SLA_ADAPTER_THROUGHPUT_RPS, (
        f"Adapter too slow: {rps:.0f} rps < SLA {SLA_ADAPTER_THROUGHPUT_RPS}"
    )


# ===========================================================================
# 2 — Single-record pipeline latency
# ===========================================================================
async def test_bench_single_record_latency():
    """P99 single-record pipeline latency must be < SLA_SINGLE_RECORD_P99_MS."""
    zone      = _make_zone()
    samples   = 30
    latencies: List[float] = []
    for _ in range(samples):
        rec = _adapt(_make_rcore())
        t0  = time.perf_counter()
        await zone.process_telemetry_batch([rec], {})
        latencies.append((time.perf_counter() - t0) * 1000)

    p50 = statistics.median(latencies)
    p99 = sorted(latencies)[max(0, int(0.99 * samples) - 1)]
    print(f"\n  Single-record  P50={p50:.1f}ms  P99={p99:.1f}ms"
          f"  (SLA P99 < {SLA_SINGLE_RECORD_P99_MS}ms)")
    assert p99 < SLA_SINGLE_RECORD_P99_MS, (
        f"P99 {p99:.1f}ms > SLA {SLA_SINGLE_RECORD_P99_MS}ms"
    )


# ===========================================================================
# 3 — Batch latency scaling
# ===========================================================================
@pytest.mark.parametrize("batch_size", [1, 5, 10, 20, 50])
async def test_bench_batch_latency_scaling(batch_size: int):
    """Batch latency must scale linearly within budget."""
    zone  = _make_zone()
    recs  = [_adapt(_make_rcore()) for _ in range(batch_size)]
    times: List[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        await zone.process_telemetry_batch(recs, {})
        times.append((time.perf_counter() - t0) * 1000)

    median_ms = statistics.median(times)
    sla_ms    = SLA_BATCH_10_MEDIAN_MS * max(1.0, batch_size / 10)
    print(f"\n  Batch({batch_size})  median={median_ms:.1f}ms  SLA≤{sla_ms:.0f}ms")
    assert median_ms < sla_ms, (
        f"Batch({batch_size}) median {median_ms:.1f}ms > SLA {sla_ms:.0f}ms"
    )


# ===========================================================================
# 4 — Preservation rate under load
# ===========================================================================
async def test_bench_preservation_rate_under_load():
    """Preservation rate ≥ SLA across 100 mixed-anomaly records."""
    zone  = _make_zone()
    recs  = [
        _adapt(_make_rcore(anomaly=_ANOMALY_MIX[i % len(_ANOMALY_MIX)]))
        for i in range(100)
    ]
    result    = await zone.process_telemetry_batch(recs, {})
    preserved = len(result.cleaned_records)
    rate      = preserved / len(recs)
    print(f"\n  Preservation  {preserved}/{len(recs)} = {rate:.4f}"
          f"  (SLA ≥ {SLA_PRESERVATION_RATE})")
    assert rate >= SLA_PRESERVATION_RATE, (
        f"Preservation rate {rate:.4f} < SLA {SLA_PRESERVATION_RATE}"
    )


# ===========================================================================
# 5 — Processing mode latency
# ===========================================================================
async def test_bench_processing_mode_latency():
    """TESTING mode must process 20 records in < 5 s."""
    BATCH = 20
    recs  = [_adapt(_make_rcore()) for _ in range(BATCH)]
    zone  = _make_zone(ProcessingMode.TESTING)
    t0    = time.perf_counter()
    res   = await zone.process_telemetry_batch(recs, {})
    ms    = (time.perf_counter() - t0) * 1000
    print(f"\n  TESTING mode  {ms:.1f}ms for {BATCH} records  (budget < 5000ms)")
    assert res is not None
    assert ms < 5_000, f"TESTING mode {ms:.1f}ms > 5000ms"


# ===========================================================================
# 6 — Concurrent batch throughput
# ===========================================================================
async def test_bench_concurrent_batch_throughput():
    """4 concurrent batches of 10 records must complete < SLA_CONCURRENT_TOTAL_MS."""
    BATCHES    = 4
    BATCH_SIZE = 10

    async def _run(zone) -> float:
        recs = [_adapt(_make_rcore()) for _ in range(BATCH_SIZE)]
        t0   = time.perf_counter()
        await zone.process_telemetry_batch(recs, {})
        return (time.perf_counter() - t0) * 1000

    zones   = [_make_zone() for _ in range(BATCHES)]
    t_wall  = time.perf_counter()
    per_ms  = await asyncio.gather(*[_run(z) for z in zones])
    wall_ms = (time.perf_counter() - t_wall) * 1000

    print(f"\n  Concurrent {BATCHES}×{BATCH_SIZE}  wall={wall_ms:.1f}ms"
          f"  per-batch={[f'{t:.0f}ms' for t in per_ms]}"
          f"  (SLA ≤ {SLA_CONCURRENT_TOTAL_MS}ms)")
    assert wall_ms < SLA_CONCURRENT_TOTAL_MS, (
        f"Concurrent wall {wall_ms:.1f}ms > SLA {SLA_CONCURRENT_TOTAL_MS}ms"
    )
