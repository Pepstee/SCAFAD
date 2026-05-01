"""
T-012 -- Contract surface test (WP-2.9, I-15)
===============================================

Permanent test.  Asserts that every public dataclass in the SCAFAD pipeline
exposes a ``to_dict()`` method whose return value is JSON-serialisable.

Invariant I-15:
    Every public dataclass defines ``to_dict()`` returning a JSON-serialisable
    dict with stable keys.  Adding a key is allowed; removing or renaming a
    key requires a Decision Log entry.

Public dataclasses covered:
    L0  -- TelemetryRecord          (layer0/app_telemetry.py)
    L1  -- Layer1ProcessedRecord    (layer1/pipeline.py)
    RT  -- CanonicalRuntimeResult   (runtime/runtime.py)

DL-026: T-012 enters permanent set (Phase 2, WP-2.9, 2026-04-20).
DL-040: imports updated to canonical scafad/ package paths.
"""

from __future__ import annotations

import json
import time
import unittest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_telemetry_record():
    from layer0.app_telemetry import (
        AnomalyType, ExecutionPhase, TelemetryRecord, TelemetrySource,
    )
    return TelemetryRecord(
        event_id="t012-event-001",
        timestamp=time.time(),
        function_id="test-function",
        execution_phase=ExecutionPhase.INVOKE,
        anomaly_type=AnomalyType.BENIGN,
        duration=0.42,
        memory_spike_kb=128,
        cpu_utilization=25.0,
        network_io_bytes=512,
        fallback_mode=False,
        source=TelemetrySource.SCAFAD_LAYER0,
        concurrency_id="conc-t012",
    )


def _make_layer1_processed_record():
    from layer0.adapter import RCoreToLayer1Adapter
    from layer1.pipeline import Layer1CanonicalPipeline
    record = _make_telemetry_record()
    adapted = RCoreToLayer1Adapter().adapt(record)
    return Layer1CanonicalPipeline().process_adapted_record(adapted)


def _make_canonical_runtime_result():
    from runtime.runtime import SCAFADCanonicalRuntime
    runtime = SCAFADCanonicalRuntime()
    event = {
        "event_id": "t012-rt-001",
        "function_id": "test-function",
        "anomaly": "benign",
        "execution_phase": "invoke",
    }
    return runtime.process_event(event)


# ---------------------------------------------------------------------------
# Mixin -- NOT a TestCase itself so pytest does not collect it directly.
# ---------------------------------------------------------------------------

class _ContractMixin:
    """Shared assertions.  Mixed into concrete TestCase subclasses."""

    obj = None
    class_label: str = ""

    def test_a_has_to_dict(self):
        self.assertTrue(  # type: ignore[attr-defined]
            hasattr(self.obj, "to_dict"),
            f"{self.class_label} must expose to_dict()",
        )
        self.assertTrue(callable(getattr(self.obj, "to_dict")))  # type: ignore

    def test_b_to_dict_returns_dict(self):
        result = self.obj.to_dict()  # type: ignore
        self.assertIsInstance(result, dict)  # type: ignore

    def test_c_to_dict_is_json_serialisable(self):
        result = self.obj.to_dict()  # type: ignore
        try:
            serialised = json.dumps(result)
        except (TypeError, ValueError) as exc:
            self.fail(  # type: ignore
                f"{self.class_label}.to_dict() is not JSON-serialisable: {exc}"
            )
        restored = json.loads(serialised)
        self.assertIsInstance(restored, dict)  # type: ignore

    def test_d_to_dict_has_stable_keys(self):
        keys_a = set(self.obj.to_dict().keys())  # type: ignore
        keys_b = set(self.obj.to_dict().keys())  # type: ignore
        self.assertEqual(keys_a, keys_b)  # type: ignore


class TestTelemetryRecordContract(_ContractMixin, unittest.TestCase):
    """T-012a -- L0 TelemetryRecord contract surface."""

    @classmethod
    def setUpClass(cls):
        cls.obj = _make_telemetry_record()
        cls.class_label = "TelemetryRecord"

    def test_e_required_keys_present(self):
        d = self.obj.to_dict()
        for key in ("event_id", "timestamp", "function_id",
                    "anomaly_type", "execution_phase"):
            self.assertIn(key, d, f"TelemetryRecord.to_dict() missing key: {key}")


class TestLayer1ProcessedRecordContract(_ContractMixin, unittest.TestCase):
    """T-012b -- L1 Layer1ProcessedRecord contract surface."""

    @classmethod
    def setUpClass(cls):
        cls.obj = _make_layer1_processed_record()
        cls.class_label = "Layer1ProcessedRecord"

    def test_e_required_keys_present(self):
        d = self.obj.to_dict()
        for key in ("record_id", "function_name", "anomaly_type",
                    "execution_phase", "schema_version"):
            self.assertIn(key, d, f"Layer1ProcessedRecord.to_dict() missing key: {key}")


class TestCanonicalRuntimeResultContract(_ContractMixin, unittest.TestCase):
    """T-012c -- CanonicalRuntimeResult contract surface."""

    @classmethod
    def setUpClass(cls):
        cls.obj = _make_canonical_runtime_result()
        cls.class_label = "CanonicalRuntimeResult"

    def test_e_required_keys_present(self):
        d = self.obj.to_dict()
        for key in ("layer0_record", "adapted_record",
                    "layer1_record", "multilayer_result"):
            self.assertIn(key, d, f"CanonicalRuntimeResult.to_dict() missing key: {key}")


if __name__ == "__main__":
    unittest.main()
