# WP-5.6 Performance Benchmark Report

**Generated:** 2026-04-24T15:52:16.779591+00:00  
**Dataset:** `datasets/synthetic_eval_dataset.json.gz`  
**Protocol:** cold_start=1 (first invocation on fresh SCAFADCanonicalRuntime), warm=100 (consecutive benign records on same instance)  

## End-to-End Latency

| Metric | Value (ms) |
|--------|-----------|
| Cold-start latency (first invocation) | 46.63 |
| Warm mean | 166.65 |
| Warm p50 (median) | 158.95 |
| Warm p95 | 386.22 |
| Warm p99 | 446.29 |
| Warm std deviation | 145.71 |
| Cold-start overhead | -120.02 ms (0.3× warm mean) |

## Layer Breakdown (warm mean, ms)

| Layer | Responsibility | Mean (ms) | Share |
|-------|---------------|-----------|-------|
| **L0** — AnomalyDetectionEngine | 26-detector panel: statistical, isolation-forest, temporal, resource | 163.36 | 98.1% |
| Adapter — RCoreToLayer1Adapter | L0→L1 schema translation (v4.2 → v2.1) | 0.11 | 0.1% |
| **L1** — Layer1CanonicalPipeline | Validate → sanitise → PII redaction → deferred hashing → preservation bounds | 2.81 | 1.7% |
| **L2–L6** — SCAFADMultilayerPipeline | Detection matrix → trust fusion → explainability → MITRE alignment → feedback | 0.28 | 0.2% |

**Slowest layer:** L0 (AnomalyDetectionEngine - 26-detector panel)

## Interpretation

The SCAFAD canonical pipeline processes a single telemetry event in **166.6 ms** (warm, arithmetic mean over 100 invocations). The warm-path p99 is 446.3 ms, indicating low tail-latency variance (stdev = 145.7 ms).

Cold-start overhead is **-120.0 ms** above the warm mean (0.3× warm latency). This is attributable to first-invocation Python module caching, L0 IsolationForest initialisation with an empty historical window, and lazy construction of internal data structures.

**L0 (AnomalyDetectionEngine - 26-detector panel)** dominates latency. L0 runs 26 detection algorithms including IsolationForest on each record; it re-fits the forest on all accumulated history every invocation, so L0 cost grows slightly with warm invocation count. L1 executes PII detection, six sanitisers, deferred hashing, and preservation-bounds calculation. L2–L6 run the multi-vector detection matrix, trust-weighted fusion, explainability decision engine, MITRE ATT&CK threat alignment, and feedback-learning signal ingestion.

## Methodology

- **Instrumentation:** `time.perf_counter()` checkpoints bracketing each layer call.
- **Cold start:** first call on a freshly instantiated `SCAFADCanonicalRuntime`.
- **Warm invocations:** 100 consecutive calls on the same runtime instance (L0 history accumulates, mimicking a short-lived warm execution environment).
- **Dataset:** benign records only, drawn in order from `datasets/synthetic_eval_dataset.json.gz` (no shuffle; reproducible).
- **Statistics:** mean, p50/median, p95, p99, stdev computed over warm invocations using linear interpolation for percentiles.
- **Verbosity:** `terse` mode passed to multilayer pipeline to suppress heavyweight explanation payloads and isolate pure compute time.
