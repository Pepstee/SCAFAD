"""
scafad/layer0/tests/test_layer0_detectors.py
=============================================

T-027 -- Layer 0 per-detector unit tests.

Exercises each of the 26 detector functions directly as standalone callables,
confirming:
  - DetectorRegistry registers all 26 algorithms at import time.
  - Every detect() function accepts the canonical signature
    (telemetry, historical_data, ml_models, config) and returns a
    well-formed DetectionResult.
  - algorithm_name in the returned result matches the registered key
    (except isolation_forest, which delegates to statistical_outlier
    when sklearn or sufficient history is unavailable).
  - No detector raises an uncaught exception on benign or empty history input.

WP-3.7: Part of the layer0_core.py decomposition (C-1 contribution).
"""
from __future__ import annotations

import time
import unittest
import uuid
from collections import deque

from layer0.app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase, TelemetrySource
from layer0.layer0_core import DetectionResult, DetectionConfig
import layer0.detectors as _detectors_pkg  # triggers all 26 registrations
from layer0.detectors.registry import REGISTRY

# Algorithms that legitimately return a different algorithm_name due to delegation.
_DELEGATING_DETECTORS = frozenset({"isolation_forest"})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_record(
    anomaly_type=AnomalyType.BENIGN,
    execution_phase=ExecutionPhase.INVOKE,
    duration=0.120,
    cpu_utilization=15.0,
    memory_spike_kb=64 * 1024,
    network_io_bytes=1024,
    adversarial_score=0.0,
    **kwargs,
):
    """Minimal valid TelemetryRecord for detector tests."""
    return TelemetryRecord(
        event_id=str(uuid.uuid4()),
        timestamp=time.time(),
        function_id="test-fn",
        execution_phase=execution_phase,
        anomaly_type=anomaly_type,
        source=TelemetrySource.SCAFAD_LAYER0,
        duration=duration,
        memory_spike_kb=memory_spike_kb,
        cpu_utilization=cpu_utilization,
        network_io_bytes=network_io_bytes,
        fallback_mode=False,
        concurrency_id="conc-001",
        adversarial_score=adversarial_score,
        economic_risk_score=0.0,
        silent_failure_probability=0.0,
        completeness_score=1.0,
        confidence_level=1.0,
        data_quality_score=1.0,
        **kwargs,
    )


def _make_history(n=30):
    """Return a deque of *n* benign TelemetryRecords spaced 1 second apart."""
    base_ts = time.time() - n
    records = deque(maxlen=10000)
    for i in range(n):
        r = _make_record(
            duration=0.100 + (i % 5) * 0.010,
            memory_spike_kb=60 * 1024 + (i % 10) * 512,
            cpu_utilization=30.0 + (i % 8),
            network_io_bytes=512 + (i % 20) * 64,
        )
        r.__dict__["timestamp"] = base_ts + i
        records.append(r)
    return records


EXPECTED_NAMES = [
    "statistical_outlier", "isolation_forest", "temporal_deviation",
    "correlation_break", "seasonal_deviation", "trend_change",
    "frequency_anomaly", "duration_outlier",
    "resource_spike", "memory_leak", "cpu_burst", "io_intensive",
    "network_anomaly", "storage_anomaly",
    "execution_pattern", "cold_start", "timeout_pattern", "error_clustering",
    "performance_regression", "concurrency_anomaly",
    "behavioral_drift", "cascade_failure", "resource_starvation",
    "security_anomaly", "dependency_failure", "economic_abuse",
]


# ---------------------------------------------------------------------------
# 1. Registry contract
# ---------------------------------------------------------------------------

class TestDetectorRegistry(unittest.TestCase):

    def test_registry_count(self):
        self.assertEqual(len(REGISTRY), 26)

    def test_registry_names_complete(self):
        self.assertEqual(set(REGISTRY.names()), set(EXPECTED_NAMES))

    def test_registry_names_ordered(self):
        self.assertEqual(REGISTRY.names(), EXPECTED_NAMES)

    def test_default_weights_positive(self):
        for name, w in REGISTRY.default_weights().items():
            self.assertGreater(w, 0.0, "%s weight must be > 0" % name)

    def test_default_weights_bounded(self):
        for name, w in REGISTRY.default_weights().items():
            self.assertLessEqual(w, 1.0, "%s weight must be <= 1.0" % name)

    def test_duplicate_registration_raises(self):
        from layer0.detectors.registry import DetectorRegistry
        reg = DetectorRegistry()
        reg.register("test_algo", 0.5, lambda t, h, m, c: None)
        with self.assertRaises(ValueError):
            reg.register("test_algo", 0.5, lambda t, h, m, c: None)

    def test_invalid_weight_raises(self):
        from layer0.detectors.registry import DetectorRegistry
        reg = DetectorRegistry()
        with self.assertRaises(ValueError):
            reg.register("bad_algo", 1.5, lambda t, h, m, c: None)


# ---------------------------------------------------------------------------
# 2. Per-detector: empty history
# ---------------------------------------------------------------------------

class TestDetectorsEmptyHistory(unittest.TestCase):

    def setUp(self):
        self.telemetry = _make_record()
        self.empty_history = deque(maxlen=10000)
        self.ml_models = {}
        self.config = DetectionConfig()

    def _check(self, algo_name, result):
        self.assertIsInstance(result, DetectionResult)
        if algo_name not in _DELEGATING_DETECTORS:
            self.assertEqual(result.algorithm_name, algo_name)
        self.assertIn(bool(result.anomaly_detected), (True, False))
        self.assertGreaterEqual(result.confidence_score, 0.0)
        self.assertLessEqual(result.confidence_score, 1.0)
        self.assertIsInstance(result.contributing_features, dict)

    def test_all_detectors_empty_history(self):
        for algo_name, (fn, _) in REGISTRY.items():
            with self.subTest(detector=algo_name):
                result = fn(self.telemetry, self.empty_history, self.ml_models, self.config)
                self._check(algo_name, result)


# ---------------------------------------------------------------------------
# 3. Per-detector: benign history (50 records)
# ---------------------------------------------------------------------------

class TestDetectorsBenignHistory(unittest.TestCase):

    def setUp(self):
        self.telemetry = _make_record()
        self.history = _make_history(50)
        self.ml_models = {}
        self.config = DetectionConfig()

    def _check(self, algo_name, result):
        self.assertIsInstance(result, DetectionResult)
        if algo_name not in _DELEGATING_DETECTORS:
            self.assertEqual(result.algorithm_name, algo_name)
        self.assertIn(bool(result.anomaly_detected), (True, False))
        self.assertGreaterEqual(result.confidence_score, 0.0)
        self.assertLessEqual(result.confidence_score, 1.0)
        self.assertGreaterEqual(result.severity, 0.0)
        self.assertLessEqual(result.severity, 1.0)
        self.assertIsNotNone(result.anomaly_type)
        self.assertIsInstance(result.explanation, str)
        self.assertIsInstance(result.contributing_features, dict)

    def test_all_detectors_benign_input(self):
        for algo_name, (fn, _) in REGISTRY.items():
            with self.subTest(detector=algo_name):
                result = fn(self.telemetry, self.history, self.ml_models, self.config)
                self._check(algo_name, result)

    def test_benign_input_low_false_positive_rate(self):
        flagged = []
        for algo_name, (fn, _) in REGISTRY.items():
            result = fn(self.telemetry, self.history, self.ml_models, self.config)
            if result.anomaly_detected:
                flagged.append(algo_name)
        fp_rate = len(flagged) / 26
        self.assertLessEqual(
            fp_rate, 0.30,
            "Too many detectors flagged benign input (%d/26): %s" % (len(flagged), flagged),
        )


# ---------------------------------------------------------------------------
# 4. Per-detector: anomalous input
# ---------------------------------------------------------------------------

class TestDetectorsAnomalousInput(unittest.TestCase):

    def setUp(self):
        self.history = _make_history(50)
        self.ml_models = {}
        self.config = DetectionConfig()

    def _get_fn(self, name):
        for n, (fn, _) in REGISTRY.items():
            if n == name:
                return fn
        self.fail("Detector not in registry: %s" % name)

    def test_resource_spike_flags_high_resource(self):
        record = _make_record(memory_spike_kb=900 * 1024, cpu_utilization=95.0)
        result = self._get_fn("resource_spike")(record, self.history, self.ml_models, self.config)
        self.assertIsInstance(result, DetectionResult)
        self.assertGreater(result.confidence_score, 0.0)

    def test_cpu_burst_flags_high_cpu(self):
        record = _make_record(cpu_utilization=98.0)
        result = self._get_fn("cpu_burst")(record, self.history, self.ml_models, self.config)
        self.assertIsInstance(result, DetectionResult)
        self.assertGreater(result.confidence_score, 0.0)

    def test_security_anomaly_flags_data_exfiltration(self):
        record = _make_record(network_io_bytes=100 * 1024 * 1024)
        result = self._get_fn("security_anomaly")(record, self.history, self.ml_models, self.config)
        self.assertIsInstance(result, DetectionResult)
        self.assertTrue(result.anomaly_detected,
                        "100 MB network transfer must trigger security_anomaly")

    def test_memory_leak_runs_on_growing_history(self):
        growing = deque(maxlen=10000)
        base_ts = time.time() - 30
        for i in range(30):
            r = _make_record(memory_spike_kb=64 * 1024 + i * 5000)
            r.__dict__["timestamp"] = base_ts + i
            growing.append(r)
        record = _make_record(memory_spike_kb=64 * 1024 + 30 * 5000)
        result = self._get_fn("memory_leak")(record, growing, self.ml_models, self.config)
        self.assertIsInstance(result, DetectionResult)


# ---------------------------------------------------------------------------
# 5. DetectionResult structural contract (I-15)
# ---------------------------------------------------------------------------

class TestDetectionResultContract(unittest.TestCase):

    def test_to_dict_returns_json_serialisable_dict(self):
        import json
        result = DetectionResult(
            algorithm_name="test", anomaly_detected=False, confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN, severity=0.0, explanation="test",
            contributing_features={}, processing_time_ms=0.0,
        )
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        json.dumps(d)

    def test_to_dict_stable_keys(self):
        result = DetectionResult(
            algorithm_name="test", anomaly_detected=True, confidence_score=0.8,
            anomaly_type=AnomalyType.CPU_BURST, severity=0.8, explanation="high cpu",
            contributing_features={"cpu": 0.8}, processing_time_ms=1.5,
        )
        d = result.to_dict()
        for key in ("algorithm_name", "anomaly_detected", "confidence_score",
                    "anomaly_type", "severity", "explanation",
                    "contributing_features", "processing_time_ms"):
            self.assertIn(key, d, "Missing key: %s" % key)
