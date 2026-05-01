"""
tests/unit/test_detector_resource_spike.py
==========================================
Unit tests for the resource_spike detector module.
WP-3.7: Each detector gets at least one unit test.
"""
from __future__ import annotations

import time
import unittest
from collections import deque

from layer0.detectors.resource_spike import detect
from layer0.detectors.registry import REGISTRY
from layer0.layer0_core import DetectionResult, DetectionConfig
from layer0.app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase, TelemetrySource


def _make_telemetry(**kwargs) -> TelemetryRecord:
    defaults = dict(
        event_id="test_001",
        timestamp=time.time(),
        function_id="test_fn",
        execution_phase=ExecutionPhase.INVOKE,
        anomaly_type=AnomalyType.BENIGN,
        duration=1.0,
        memory_spike_kb=1024,
        cpu_utilization=25.0,
        network_io_bytes=500,
        fallback_mode=False,
        source=TelemetrySource.SCAFAD_LAYER0,
        concurrency_id='test-concurrency-id',
    )
    defaults.update(kwargs)
    return TelemetryRecord(**defaults)


class TestResourceSpikeDetector(unittest.TestCase):

    def setUp(self):
        self.config = DetectionConfig()
        self.ml_models = {}
        self.telemetry = _make_telemetry()

    def test_registered_in_registry(self):
        """resource_spike must be registered in the DetectorRegistry."""
        self.assertIn('resource_spike', REGISTRY)

    def test_returns_detection_result_with_no_history(self):
        """With empty historical_data, detect must return a benign DetectionResult."""
        result = detect(self.telemetry, deque(), self.ml_models, self.config)
        self.assertIsInstance(result, DetectionResult)
        self.assertEqual(result.algorithm_name, "resource_spike")
        self.assertFalse(result.anomaly_detected)
        self.assertIsInstance(result.confidence_score, float)

    def test_result_confidence_in_range(self):
        """confidence_score must be in [0, 1]."""
        result = detect(self.telemetry, deque(), self.ml_models, self.config)
        self.assertGreaterEqual(result.confidence_score, 0.0)
        self.assertLessEqual(result.confidence_score, 1.0)

    def test_to_dict_is_serialisable(self):
        """to_dict() must return a JSON-serialisable structure."""
        import json
        result = detect(self.telemetry, deque(), self.ml_models, self.config)
        d = result.to_dict()
        json.dumps(d)  # must not raise


if __name__ == "__main__":
    unittest.main()
