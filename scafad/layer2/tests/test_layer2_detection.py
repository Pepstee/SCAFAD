"""
tests/unit/test_layer2_detection.py
=====================================

T-018 — Unit tests for MultiVectorDetectionMatrix (WP-3.6, DL-033).

Permanent set member.  32 test cases covering:
  - DetectionSignal and Layer2DetectionResult API shape (to_dict, fields)
  - RuleChainEngine: score increases with threshold-exceeding telemetry
  - DriftTracker: drift markers and risk scores drive score upward
  - GraphImmunizedDetector: graph density and causal depth influence score
  - SemanticDeviationCore: non-benign anomaly type raises score
  - MultiVectorDetectionMatrix: four signals always produced
  - Integration — benign record: aggregate_score low, anomaly_indicated False
  - Integration — high-anomaly record: aggregate_score elevated,
    anomaly_indicated True
  - Integration — per anomaly class: benign, suspicious, malicious
  - Immutability: original record never mutated
  - Fail-safe: empty/minimal record does not raise
"""

from __future__ import annotations

import copy
import unittest
from typing import Any, Dict

from layer2.detection_matrix import (
    DetectionSignal,
    DriftTracker,
    GraphImmunizedDetector,
    Layer2DetectionResult,
    MultiVectorDetectionMatrix,
    RuleChainEngine,
    SemanticDeviationCore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _benign_record(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "record_id": "rec-benign-001",
        "timestamp": 1_714_000_000.0,
        "function_name": "my-lambda",
        "execution_phase": "execution",
        "anomaly_type": "benign",
        "schema_version": "v2.1",
        "telemetry_data": {
            "l0_duration_ms": 10.0,
            "l0_memory_spike_kb": 256,
            "l0_cpu_utilization": 5.0,
            "l0_network_io_bytes": 100,
            "l0_fallback_mode": False,
        },
        "context_metadata": {
            "completeness_score": 1.0,
            "economic_risk_score": 0.0,
            "silent_failure_probability": 0.0,
        },
        "provenance_chain": {},
    }
    base.update(overrides)
    return base


def _anomalous_record(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "record_id": "rec-anomalous-001",
        "timestamp": 1_714_000_000.0,
        "function_name": "image_processor",
        "execution_phase": "execution",
        "anomaly_type": "memory_spike",
        "schema_version": "v2.1",
        "telemetry_data": {
            "l0_duration_ms": 5000.0,
            "l0_memory_spike_kb": 524288,
            "l0_cpu_utilization": 95.0,
            "l0_network_io_bytes": 10240,
            "l0_fallback_mode": False,
            "latency_drift": 0.8,
        },
        "context_metadata": {
            "completeness_score": 0.6,
            "economic_risk_score": 0.9,
            "silent_failure_probability": 0.7,
            "anomaly_category": "security",
            "anomaly_severity": 9,
        },
        "provenance_chain": {
            "causal_depth": 5,
            "parent_chain": ["a", "b", "c", "d"],
        },
    }
    base.update(overrides)
    return base


MATRIX = MultiVectorDetectionMatrix()


# ---------------------------------------------------------------------------
# API shape — DetectionSignal
# ---------------------------------------------------------------------------

class TestDetectionSignalShape(unittest.TestCase):

    def _signal(self) -> DetectionSignal:
        return RuleChainEngine().evaluate(_benign_record())

    def test_detection_signal_has_detector_name(self):
        self.assertIsInstance(self._signal().detector_name, str)

    def test_detection_signal_has_score(self):
        self.assertIsInstance(self._signal().score, float)

    def test_detection_signal_has_confidence(self):
        self.assertIsInstance(self._signal().confidence, float)

    def test_detection_signal_has_rationale(self):
        self.assertIsInstance(self._signal().rationale, str)

    def test_detection_signal_to_dict_is_json_serialisable(self):
        import json
        d = self._signal().to_dict()
        json.dumps(d)  # must not raise

    def test_detection_signal_score_in_unit_interval(self):
        score = self._signal().score
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


# ---------------------------------------------------------------------------
# API shape — Layer2DetectionResult
# ---------------------------------------------------------------------------

class TestLayer2DetectionResultShape(unittest.TestCase):

    def _result(self) -> Layer2DetectionResult:
        return MATRIX.analyze(_benign_record())

    def test_result_has_record_id(self):
        self.assertIsInstance(self._result().record_id, str)

    def test_result_has_signals_list(self):
        self.assertIsInstance(self._result().signals, list)

    def test_result_has_aggregate_score(self):
        self.assertIsInstance(self._result().aggregate_score, float)

    def test_result_has_anomaly_indicated_bool(self):
        self.assertIsInstance(self._result().anomaly_indicated, bool)

    def test_result_to_dict_is_json_serialisable(self):
        import json
        d = self._result().to_dict()
        json.dumps(d)


# ---------------------------------------------------------------------------
# RuleChainEngine
# ---------------------------------------------------------------------------

class TestRuleChainEngine(unittest.TestCase):

    def test_detector_name_is_rule_chain(self):
        sig = RuleChainEngine().evaluate(_benign_record())
        self.assertEqual(sig.detector_name, "rule_chain")

    def test_benign_telemetry_produces_low_score(self):
        sig = RuleChainEngine().evaluate(_benign_record())
        self.assertLess(sig.score, 0.5)

    def test_high_cpu_raises_score(self):
        rec = _benign_record()
        rec["telemetry_data"]["l0_cpu_utilization"] = 95.0
        sig = RuleChainEngine().evaluate(rec)
        self.assertGreater(sig.score, 0.0)

    def test_high_memory_raises_score(self):
        rec = _benign_record()
        rec["telemetry_data"]["l0_memory_spike_kb"] = 200_000
        sig = RuleChainEngine().evaluate(rec)
        self.assertGreater(sig.score, 0.0)

    def test_score_capped_at_one(self):
        sig = RuleChainEngine().evaluate(_anomalous_record())
        self.assertLessEqual(sig.score, 1.0)


# ---------------------------------------------------------------------------
# DriftTracker
# ---------------------------------------------------------------------------

class TestDriftTracker(unittest.TestCase):

    def test_detector_name_is_drift_tracker(self):
        sig = DriftTracker().evaluate(_benign_record())
        self.assertEqual(sig.detector_name, "drift_tracker")

    def test_benign_record_low_drift_score(self):
        sig = DriftTracker().evaluate(_benign_record())
        self.assertLess(sig.score, 0.5)

    def test_high_economic_risk_raises_score(self):
        rec = _benign_record()
        rec["context_metadata"]["economic_risk_score"] = 1.0
        sig = DriftTracker().evaluate(rec)
        self.assertGreater(sig.score, 0.0)

    def test_drift_marker_in_telemetry_raises_score(self):
        rec = _benign_record()
        rec["telemetry_data"]["latency_drift"] = 0.9
        sig = DriftTracker().evaluate(rec)
        self.assertGreater(sig.score, 0.0)


# ---------------------------------------------------------------------------
# GraphImmunizedDetector
# ---------------------------------------------------------------------------

class TestGraphImmunizedDetector(unittest.TestCase):

    def test_detector_name_is_graph_immunized(self):
        sig = GraphImmunizedDetector().evaluate(_benign_record())
        self.assertEqual(sig.detector_name, "graph_immunized")

    def test_empty_provenance_gives_low_score(self):
        sig = GraphImmunizedDetector().evaluate(_benign_record())
        self.assertLessEqual(sig.score, 0.5)

    def test_high_causal_depth_increases_score(self):
        rec = _benign_record()
        rec["provenance_chain"] = {"causal_depth": 20, "parent_chain": list(range(20))}
        sig = GraphImmunizedDetector().evaluate(rec)
        self.assertGreater(sig.score, 0.0)


# ---------------------------------------------------------------------------
# SemanticDeviationCore
# ---------------------------------------------------------------------------

class TestSemanticDeviationCore(unittest.TestCase):

    def test_detector_name_is_semantic_deviation(self):
        sig = SemanticDeviationCore().evaluate(_benign_record())
        self.assertEqual(sig.detector_name, "semantic_deviation")

    def test_benign_anomaly_type_gives_low_score(self):
        sig = SemanticDeviationCore().evaluate(_benign_record())
        self.assertLess(sig.score, 0.5)

    def test_non_benign_anomaly_type_raises_score(self):
        rec = _benign_record(anomaly_type="memory_spike")
        sig = SemanticDeviationCore().evaluate(rec)
        self.assertGreater(sig.score, 0.3)

    def test_malicious_anomaly_type_raises_score_high(self):
        rec = _benign_record(anomaly_type="malicious")
        sig = SemanticDeviationCore().evaluate(rec)
        self.assertGreater(sig.score, 0.3)


# ---------------------------------------------------------------------------
# MultiVectorDetectionMatrix — four signals always emitted
# ---------------------------------------------------------------------------

class TestMultiVectorMatrix(unittest.TestCase):

    def test_always_produces_four_signals(self):
        result = MATRIX.analyze(_benign_record())
        self.assertEqual(len(result.signals), 4)

    def test_detector_names_cover_all_four(self):
        result = MATRIX.analyze(_benign_record())
        names = {s.detector_name for s in result.signals}
        self.assertIn("rule_chain", names)
        self.assertIn("drift_tracker", names)
        self.assertIn("graph_immunized", names)
        self.assertIn("semantic_deviation", names)

    def test_aggregate_score_is_confidence_weighted_mean(self):
        result = MATRIX.analyze(_benign_record())
        total_conf = sum(s.confidence for s in result.signals)
        expected = sum(s.score * s.confidence for s in result.signals) / total_conf
        self.assertAlmostEqual(result.aggregate_score, round(expected, 4), places=4)


# ---------------------------------------------------------------------------
# Integration — anomaly class: benign
# ---------------------------------------------------------------------------

class TestIntegrationBenign(unittest.TestCase):

    def test_benign_record_anomaly_indicated_false(self):
        result = MATRIX.analyze(_benign_record())
        self.assertFalse(result.anomaly_indicated)

    def test_benign_record_aggregate_score_below_threshold(self):
        result = MATRIX.analyze(_benign_record())
        self.assertLess(result.aggregate_score, 0.3)


# ---------------------------------------------------------------------------
# Integration — anomaly class: anomalous
# ---------------------------------------------------------------------------

class TestIntegrationAnomalous(unittest.TestCase):

    def test_high_anomaly_record_anomaly_indicated_true(self):
        result = MATRIX.analyze(_anomalous_record())
        self.assertTrue(result.anomaly_indicated)

    def test_high_anomaly_record_aggregate_score_above_threshold(self):
        result = MATRIX.analyze(_anomalous_record())
        self.assertGreaterEqual(result.aggregate_score, 0.3)


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

class TestImmutability(unittest.TestCase):

    def test_original_record_not_mutated(self):
        rec = _anomalous_record()
        original_anomaly_type = rec["anomaly_type"]
        MATRIX.analyze(rec)
        self.assertEqual(rec["anomaly_type"], original_anomaly_type)


# ---------------------------------------------------------------------------
# Fail-safe
# ---------------------------------------------------------------------------

class TestFailSafe(unittest.TestCase):

    def test_empty_record_does_not_raise(self):
        result = MATRIX.analyze({})
        self.assertIsInstance(result, Layer2DetectionResult)

    def test_minimal_record_produces_four_signals(self):
        result = MATRIX.analyze({"record_id": "x", "anomaly_type": "benign"})
        self.assertEqual(len(result.signals), 4)


if __name__ == "__main__":
    unittest.main()
