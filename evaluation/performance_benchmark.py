#!/usr/bin/env python3
"""
WP-5.6: Performance Benchmark — Cold-Start and Warm Invocation Latency
=======================================================================

Measures end-to-end latency of the SCAFAD canonical pipeline (L0 through L6)
using benign records from the synthetic evaluation dataset.

Cold start: first invocation on a freshly constructed SCAFADCanonicalRuntime.
Warm:       100 consecutive invocations on the same runtime instance.

Layer breakdown times each sub-call inside process_record():
  - L0  : AnomalyDetectionEngine._enrich_record()   (26-detector panel)
  - L1  : Layer1CanonicalPipeline.process_adapted_record()
           (validation → sanitisation → privacy → hashing → preservation)
  - L2–6: SCAFADMultilayerPipeline.process_record()
           (detection matrix → trust fusion → explainability →
            threat alignment → feedback learning)

Outputs
-------
  evaluation/results/performance_benchmark.json  — machine-readable stats
  evaluation/results/performance_report.md       — human-readable summary

Usage
-----
    cd project/scafad-r-core
    python evaluation/performance_benchmark.py

Public API (importable by the test suite)
-----------------------------------------
    from evaluation.performance_benchmark import run_benchmark, percentile
"""

from __future__ import annotations

import gzip
import importlib
import importlib.abc
import importlib.machinery
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Path bootstrap — mirrors run_scafad_pipeline.py
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent    # .../evaluation/
_REPO_ROOT = _SCRIPT_DIR.parent                  # .../scafad-r-core/
_SCAFAD_PKG = _REPO_ROOT / "scafad"

for _p in (str(_REPO_ROOT), str(_SCAFAD_PKG)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Namespace alias hook (DL-040) — ensures scafad.layerX and layerX resolve
# to the same class objects.
# ---------------------------------------------------------------------------

class _AliasLoader(importlib.abc.Loader):
    def __init__(self, module: object) -> None:
        self._module = module

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> object:  # noqa: ARG002
        return self._module

    def exec_module(self, module: object) -> None:  # noqa: ARG002
        pass


class _ScafadNamespaceAlias(importlib.abc.MetaPathFinder):
    _PREFIX = "scafad."
    _LAYERS = frozenset(
        ["layer0", "layer1", "layer2", "layer3", "layer4", "layer5", "layer6", "runtime"]
    )

    def find_spec(
        self,
        fullname: str,
        path: object,  # noqa: ARG002
        target: object = None,  # noqa: ARG002
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith(self._PREFIX):
            return None
        rest = fullname[len(self._PREFIX):]
        top_layer = rest.split(".")[0]
        if top_layer not in self._LAYERS:
            return None
        if fullname in sys.modules:
            return None
        if rest not in sys.modules:
            try:
                importlib.import_module(rest)
            except ImportError:
                return None
        bare_mod = sys.modules.get(rest)
        if bare_mod is None:
            return None
        sys.modules[fullname] = bare_mod
        spec = importlib.machinery.ModuleSpec(fullname, _AliasLoader(bare_mod))
        spec.submodule_search_locations = getattr(bare_mod, "__path__", None)
        return spec


if not any(isinstance(f, _ScafadNamespaceAlias) for f in sys.meta_path):
    sys.meta_path.insert(0, _ScafadNamespaceAlias())

import logging  # noqa: E402

# Suppress SCAFAD internal noise during benchmarking.
logging.basicConfig(level=logging.WARNING)
for _noisy in ("layer0", "layer1", "layer2", "layer3", "layer4", "layer5",
               "layer6", "runtime", "SCAFAD"):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

from runtime.runtime import SCAFADCanonicalRuntime  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATASET_PATH = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
OUTPUT_JSON = _REPO_ROOT / "evaluation" / "results" / "performance_benchmark.json"
OUTPUT_REPORT = _REPO_ROOT / "evaluation" / "results" / "performance_report.md"

WARM_INVOCATIONS: int = 100
BENIGN_CLASS: str = "benign"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_benign_records(n: int = WARM_INVOCATIONS + 1) -> List[Dict[str, Any]]:
    """Return the first *n* benign records from the synthetic evaluation dataset.

    Parameters
    ----------
    n:
        Maximum number of records to return.  The dataset contains 250 benign
        records so n ≤ 250 is always satisfiable.

    Returns
    -------
    list
        List of raw event dictionaries suitable for SCAFADCanonicalRuntime.process_event().
    """
    with gzip.open(str(DATASET_PATH), "rt", encoding="utf-8") as fh:
        all_records: List[Dict[str, Any]] = json.load(fh)
    benign = [r for r in all_records if r.get("anomaly_type", "").lower() == BENIGN_CLASS]
    return benign[:n]


# ---------------------------------------------------------------------------
# Instrumented single-record execution
# ---------------------------------------------------------------------------

def _run_instrumented(
    runtime: SCAFADCanonicalRuntime,
    event: Dict[str, Any],
) -> Dict[str, float]:
    """Execute one event through the full pipeline with per-layer timing.

    Mirrors the body of SCAFADCanonicalRuntime.process_record() exactly, using
    time.perf_counter() checkpoints between each sub-call.  The runtime's own
    ``process_event`` is intentionally bypassed so the timing brackets are
    placed at the correct granularity.

    Parameters
    ----------
    runtime:
        A fully initialised SCAFADCanonicalRuntime instance.
    event:
        Raw event dictionary to process.

    Returns
    -------
    dict with keys:
        total_ms    — wall time for the full pipeline (ms)
        build_ms    — record construction time (ms)
        l0_ms       — L0 enrichment / anomaly detection (ms)
        adapter_ms  — L0→L1 schema adaptation (ms)
        l1_ms       — L1 pipeline (validate/sanitise/hash/preserve) (ms)
        l2_to_l6_ms — Multilayer pipeline L2–L6 (ms)
    """
    t0 = time.perf_counter()

    # Build TelemetryRecord from raw event dict
    record = runtime.build_record(event)
    t_build = time.perf_counter()

    # L0: run 26-detector panel; writes back adversarial/economic/silent_failure scores
    record = runtime._enrich_record(record)  # noqa: SLF001
    t_l0 = time.perf_counter()

    # Adapter: translate L0 TelemetryRecord → L1 dict (schema v2.1)
    adapted = runtime.adapter.adapt(record)
    t_adapter = time.perf_counter()

    # L1: InputValidationGateway → SanitisationProcessor → PrivacyComplianceFilter
    #     → DeferredHashingManager → assess_preservation
    layer1_record = runtime.layer1_pipeline.process_adapted_record(adapted)
    t_l1 = time.perf_counter()

    # L2–L6: MultiVectorDetectionMatrix → TrustWeightedFusionEngine
    #         → ExplainabilityDecisionEngine → ThreatAlignmentEngine
    #         → FeedbackLearningEngine
    runtime.multilayer_pipeline.process_record(layer1_record, verbosity="terse")
    t_end = time.perf_counter()

    def _ms(ta: float, tb: float) -> float:
        return round((tb - ta) * 1000.0, 4)

    return {
        "total_ms":    _ms(t0,        t_end),
        "build_ms":    _ms(t0,        t_build),
        "l0_ms":       _ms(t_build,   t_l0),
        "adapter_ms":  _ms(t_l0,      t_adapter),
        "l1_ms":       _ms(t_adapter, t_l1),
        "l2_to_l6_ms": _ms(t_l1,     t_end),
    }


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def percentile(data: List[float], p: float) -> float:
    """Compute the *p*-th percentile of *data* using linear interpolation.

    Parameters
    ----------
    data:
        List of numeric values (need not be sorted).
    p:
        Percentile in [0, 100].

    Returns
    -------
    float
        The interpolated p-th percentile value.
    """
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 0:
        return 0.0
    if n == 1:
        return round(sorted_data[0], 4)
    idx = (p / 100.0) * (n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return round(sorted_data[lo], 4)
    frac = idx - lo
    return round(sorted_data[lo] * (1.0 - frac) + sorted_data[hi] * frac, 4)


# ---------------------------------------------------------------------------
# Core benchmark
# ---------------------------------------------------------------------------

def run_benchmark(
    warm_invocations: int = WARM_INVOCATIONS,
    dataset_path: Path = DATASET_PATH,
) -> Dict[str, Any]:
    """Run the full performance benchmark and return a results dictionary.

    The benchmark proceeds in two phases:

    1. **Cold start** — instantiate a fresh SCAFADCanonicalRuntime and time
       the first process_event() call.  This captures first-invocation overhead
       (lazy L0 IsolationForest fitting on empty history, Python import caches,
       JIT-like optimisations).

    2. **Warm invocations** — time *warm_invocations* consecutive calls on the
       same runtime instance.  Statistics (mean, p50, p95, p99) are computed
       over these measurements.

    Parameters
    ----------
    warm_invocations:
        Number of warm invocations to measure.  Default: 100.
    dataset_path:
        Path to the gzip-compressed synthetic evaluation dataset.

    Returns
    -------
    dict
        JSON-serialisable results dictionary matching the output schema:
        ``{cold_start_ms, warm_mean_ms, warm_p50_ms, warm_p95_ms, warm_p99_ms,
           layer_breakdown: {l0_ms, l1_ms, l2_to_l6_ms}, ...}``
    """
    print("[WP-5.6] Loading benign records from dataset...", flush=True)
    # Need at least warm_invocations + 1 records: 1 for cold start, rest for warm.
    records = _load_benign_records_from(dataset_path, warm_invocations + 1)
    actual_warm = min(warm_invocations, len(records) - 1)
    print(
        f"[WP-5.6] Loaded {len(records)} benign records; "
        f"warm invocations = {actual_warm}.",
        flush=True,
    )

    # ------------------------------------------------------------------
    # Phase 1: Cold start
    # ------------------------------------------------------------------
    print("[WP-5.6] Phase 1 - cold-start invocation...", flush=True)
    runtime = SCAFADCanonicalRuntime()
    cold_result = _run_instrumented(runtime, records[0])
    cold_start_ms = cold_result["total_ms"]
    print(f"[WP-5.6] Cold start: {cold_start_ms:.2f} ms", flush=True)

    # ------------------------------------------------------------------
    # Phase 2: Warm invocations (same runtime instance)
    # ------------------------------------------------------------------
    print(
        f"[WP-5.6] Phase 2 - {actual_warm} warm invocations...",
        flush=True,
    )
    warm_results: List[Dict[str, float]] = []
    t_phase2_start = time.perf_counter()

    for i in range(actual_warm):
        rec = records[1 + i]  # skip record 0 (used for cold start)
        result = _run_instrumented(runtime, rec)
        warm_results.append(result)
        if (i + 1) % 10 == 0:
            elapsed = time.perf_counter() - t_phase2_start
            print(
                f"  [{i + 1:3d}/{actual_warm}]  "
                f"last={result['total_ms']:.1f} ms  "
                f"elapsed={elapsed:.1f}s",
                flush=True,
            )

    # ------------------------------------------------------------------
    # Aggregate statistics
    # ------------------------------------------------------------------
    warm_totals: List[float] = [r["total_ms"] for r in warm_results]
    warm_l0: List[float] = [r["l0_ms"] for r in warm_results]
    warm_adapter: List[float] = [r["adapter_ms"] for r in warm_results]
    warm_l1: List[float] = [r["l1_ms"] for r in warm_results]
    warm_multilayer: List[float] = [r["l2_to_l6_ms"] for r in warm_results]

    warm_mean_ms = round(statistics.mean(warm_totals), 4)
    warm_p50_ms = percentile(warm_totals, 50)
    warm_p95_ms = percentile(warm_totals, 95)
    warm_p99_ms = percentile(warm_totals, 99)
    warm_stdev_ms = round(statistics.stdev(warm_totals), 4) if len(warm_totals) > 1 else 0.0

    l0_mean_ms = round(statistics.mean(warm_l0), 4)
    adapter_mean_ms = round(statistics.mean(warm_adapter), 4)
    l1_mean_ms = round(statistics.mean(warm_l1), 4)
    multilayer_mean_ms = round(statistics.mean(warm_multilayer), 4)

    cold_overhead_ms = round(cold_start_ms - warm_mean_ms, 4)
    cold_overhead_factor = round(cold_start_ms / warm_mean_ms, 2) if warm_mean_ms > 0 else 0.0

    # Identify the slowest layer by mean ms (excluding build_ms which is shared overhead)
    layer_means: Dict[str, float] = {
        "L0 (AnomalyDetectionEngine - 26-detector panel)": l0_mean_ms,
        "L1 (Layer1CanonicalPipeline - validate/sanitise/hash/preserve)": l1_mean_ms,
        "L2-L6 (SCAFADMultilayerPipeline - detection/fusion/explain/threat/feedback)": multilayer_mean_ms,
    }
    slowest_layer = max(layer_means, key=layer_means.__getitem__)

    # Print summary
    print("\n[WP-5.6] -- Benchmark Results --", flush=True)
    print(f"  Cold start       : {cold_start_ms:.2f} ms", flush=True)
    print(f"  Warm mean        : {warm_mean_ms:.2f} ms", flush=True)
    print(f"  Warm p50 (median): {warm_p50_ms:.2f} ms", flush=True)
    print(f"  Warm p95         : {warm_p95_ms:.2f} ms", flush=True)
    print(f"  Warm p99         : {warm_p99_ms:.2f} ms", flush=True)
    print(f"  Warm stdev       : {warm_stdev_ms:.2f} ms", flush=True)
    print(f"  Cold overhead    : {cold_overhead_ms:.2f} ms ({cold_overhead_factor:.1f}x)", flush=True)
    print("  -- Layer Breakdown (warm mean) --", flush=True)
    print(f"  L0  (26-detector): {l0_mean_ms:.2f} ms", flush=True)
    print(f"  Adapter (L0->L1) : {adapter_mean_ms:.2f} ms", flush=True)
    print(f"  L1  (pipeline)   : {l1_mean_ms:.2f} ms", flush=True)
    print(f"  L2-6 (multilayer): {multilayer_mean_ms:.2f} ms", flush=True)
    print(f"  Slowest layer    : {slowest_layer}", flush=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "datasets/synthetic_eval_dataset.json.gz",
        "protocol": (
            f"cold_start=1 (first invocation on fresh SCAFADCanonicalRuntime), "
            f"warm={actual_warm} (consecutive benign records on same instance)"
        ),
        "warm_invocations": actual_warm,
        # Primary output schema (matches task specification)
        "cold_start_ms": cold_start_ms,
        "warm_mean_ms": warm_mean_ms,
        "warm_p50_ms": warm_p50_ms,
        "warm_p95_ms": warm_p95_ms,
        "warm_p99_ms": warm_p99_ms,
        # Derived statistics
        "warm_stdev_ms": warm_stdev_ms,
        "warm_min_ms": round(min(warm_totals), 4),
        "warm_max_ms": round(max(warm_totals), 4),
        "cold_overhead_ms": cold_overhead_ms,
        "cold_overhead_factor": cold_overhead_factor,
        # Layer breakdown (warm means, per task output schema)
        "layer_breakdown": {
            "l0_ms": l0_mean_ms,
            "adapter_ms": adapter_mean_ms,
            "l1_ms": l1_mean_ms,
            "l2_to_l6_ms": multilayer_mean_ms,
        },
        "slowest_layer": slowest_layer,
        # Raw warm timings for reproducibility / downstream analysis
        "warm_raw_ms": warm_totals,
        # Per-layer raw timings
        "warm_layer_raw_ms": {
            "l0": warm_l0,
            "adapter": warm_adapter,
            "l1": warm_l1,
            "l2_to_l6": warm_multilayer,
        },
    }


def _load_benign_records_from(
    dataset_path: Path, n: int
) -> List[Dict[str, Any]]:
    """Internal helper: load first *n* benign records from *dataset_path*."""
    with gzip.open(str(dataset_path), "rt", encoding="utf-8") as fh:
        all_records: List[Dict[str, Any]] = json.load(fh)
    benign = [r for r in all_records if r.get("anomaly_type", "").lower() == BENIGN_CLASS]
    return benign[:n]


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(results: Dict[str, Any], report_path: Path) -> None:
    """Write a human-readable Markdown performance report.

    Parameters
    ----------
    results:
        Dictionary returned by run_benchmark().
    report_path:
        Destination path for the Markdown file.
    """
    lb = results["layer_breakdown"]
    l0_ms: float = lb["l0_ms"]
    adapter_ms: float = lb["adapter_ms"]
    l1_ms: float = lb["l1_ms"]
    l2l6_ms: float = lb["l2_to_l6_ms"]
    total_layer_ms = l0_ms + adapter_ms + l1_ms + l2l6_ms

    def _pct(v: float) -> str:
        if total_layer_ms <= 0:
            return "N/A"
        return f"{v / total_layer_ms * 100:.1f}%"

    cold_ms: float = results["cold_start_ms"]
    warm_mean: float = results["warm_mean_ms"]
    warm_p50: float = results["warm_p50_ms"]
    warm_p95: float = results["warm_p95_ms"]
    warm_p99: float = results["warm_p99_ms"]
    warm_stdev: float = results.get("warm_stdev_ms", 0.0)
    cold_oh: float = results["cold_overhead_ms"]
    cold_factor: float = results["cold_overhead_factor"]
    slowest: str = results["slowest_layer"]
    n_warm: int = results["warm_invocations"]

    lines: List[str] = [
        "# WP-5.6 Performance Benchmark Report",
        "",
        f"**Generated:** {results['generated_at']}  ",
        f"**Dataset:** `{results['dataset']}`  ",
        f"**Protocol:** {results['protocol']}  ",
        "",
        "## End-to-End Latency",
        "",
        "| Metric | Value (ms) |",
        "|--------|-----------|",
        f"| Cold-start latency (first invocation) | {cold_ms:.2f} |",
        f"| Warm mean | {warm_mean:.2f} |",
        f"| Warm p50 (median) | {warm_p50:.2f} |",
        f"| Warm p95 | {warm_p95:.2f} |",
        f"| Warm p99 | {warm_p99:.2f} |",
        f"| Warm std deviation | {warm_stdev:.2f} |",
        f"| Cold-start overhead | {cold_oh:.2f} ms ({cold_factor:.1f}× warm mean) |",
        "",
        "## Layer Breakdown (warm mean, ms)",
        "",
        "| Layer | Responsibility | Mean (ms) | Share |",
        "|-------|---------------|-----------|-------|",
        f"| **L0** — AnomalyDetectionEngine | 26-detector panel: statistical, isolation-forest, temporal, resource | {l0_ms:.2f} | {_pct(l0_ms)} |",
        f"| Adapter — RCoreToLayer1Adapter | L0→L1 schema translation (v4.2 → v2.1) | {adapter_ms:.2f} | {_pct(adapter_ms)} |",
        f"| **L1** — Layer1CanonicalPipeline | Validate → sanitise → PII redaction → deferred hashing → preservation bounds | {l1_ms:.2f} | {_pct(l1_ms)} |",
        f"| **L2–L6** — SCAFADMultilayerPipeline | Detection matrix → trust fusion → explainability → MITRE alignment → feedback | {l2l6_ms:.2f} | {_pct(l2l6_ms)} |",
        "",
        f"**Slowest layer:** {slowest}",
        "",
        "## Interpretation",
        "",
        (
            f"The SCAFAD canonical pipeline processes a single telemetry event in "
            f"**{warm_mean:.1f} ms** (warm, arithmetic mean over {n_warm} invocations). "
            f"The warm-path p99 is {warm_p99:.1f} ms, indicating low tail-latency variance "
            f"(stdev = {warm_stdev:.1f} ms)."
        ),
        "",
        (
            f"Cold-start overhead is **{cold_oh:.1f} ms** above the warm mean "
            f"({cold_factor:.1f}× warm latency). This is attributable to first-invocation "
            "Python module caching, L0 IsolationForest initialisation with an empty "
            "historical window, and lazy construction of internal data structures."
        ),
        "",
        (
            f"**{slowest}** dominates latency. "
            "L0 runs 26 detection algorithms including IsolationForest on each record; "
            "it re-fits the forest on all accumulated history every invocation, so L0 "
            "cost grows slightly with warm invocation count. "
            "L1 executes PII detection, six sanitisers, deferred hashing, and "
            "preservation-bounds calculation. "
            "L2–L6 run the multi-vector detection matrix, trust-weighted fusion, "
            "explainability decision engine, MITRE ATT&CK threat alignment, "
            "and feedback-learning signal ingestion."
        ),
        "",
        "## Methodology",
        "",
        "- **Instrumentation:** `time.perf_counter()` checkpoints bracketing each layer call.",
        f"- **Cold start:** first call on a freshly instantiated `SCAFADCanonicalRuntime`.",
        f"- **Warm invocations:** {n_warm} consecutive calls on the same runtime instance "
        "(L0 history accumulates, mimicking a short-lived warm execution environment).",
        "- **Dataset:** benign records only, drawn in order from "
        "`datasets/synthetic_eval_dataset.json.gz` (no shuffle; reproducible).",
        "- **Statistics:** mean, p50/median, p95, p99, stdev computed over warm "
        "invocations using linear interpolation for percentiles.",
        "- **Verbosity:** `terse` mode passed to multilayer pipeline to suppress "
        "heavyweight explanation payloads and isolate pure compute time.",
        "",
    ]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(report_path), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"[WP-5.6] Report written -> {report_path}", flush=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point: run benchmark and write both output files."""
    results = run_benchmark()

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(str(OUTPUT_JSON), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"[WP-5.6] JSON written -> {OUTPUT_JSON}", flush=True)

    write_report(results, OUTPUT_REPORT)
    print("[WP-5.6] Done.", flush=True)


if __name__ == "__main__":
    main()
