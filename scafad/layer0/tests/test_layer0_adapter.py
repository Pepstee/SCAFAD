"""
T-019 — Layer 0 adapter unit tests.

Covers RCoreToLayer1Adapter.adapt() — the sole authorised translation
point between L0 TelemetryRecord and the L1 intake contract.

WP: Day-1 restructuring (T-019)
"""

from __future__ import annotations

import unittest
import uuid
from typing import Any, Dict

from layer0.adapter import (
    ADAPTER_VERSION,
    ERROR_STACK_PLACEHOLDER,
    TARGET_LAYER1_SCHEMA_VERSION,
    RCoreToLayer1Adapter,
)
from layer0.app_telemetry import AnomalyType, ExecutionPhase, TelemetryRecord, TelemetrySource


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_record(**kwargs: Any) -> TelemetryRecord:
    """Return a minimal valid TelemetryRecord; override any field via kwargs."""
    defaults: Dict[str, Any] = dict(
        event_id=str(uuid.uuid4()),
        timestamp=1_700_000_000.0,
        function_id="my-lambda",
        anomaly_type=AnomalyType.BENIGN,
        execution_phase=ExecutionPhase.INVOKE,
        source=TelemetrySource.PRIMARY,
        duration=120.0,
        memory_spike_kb=0,
        cpu_utilization=0.1,
        network_io_bytes=0,
        fallback_mode=False,
        concurrency_id="conc-1",
    )
    defaults.update(kwargs)
    return TelemetryRecord(**defaults)


# ---------------------------------------------------------------------------
# Test: output shape
# ---------------------------------------------------------------------------

class TestAdapterOutputShape(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = RCoreToLayer1Adapter()
        self.adapted = self.adapter.adapt(_make_record())

    def test_required_top_level_keys_present(self) -> None:
        required = {
            "record_id", "timestamp", "function_name", "execution_phase",
            "anomaly_type", "telemetry_data", "provenance_chain",
            "context_metadata", "schema_version",
        }
        self.assertTrue(required.issubset(self.adapted.keys()),
                        f"Missing keys: {required - self.adapted.keys()}")

    def test_schema_version_equals_target(self) -> None:
        self.assertEqual(self.adapted["schema_version"], TARGET_LAYER1_SCHEMA_VERSION)

    def test_record_id_is_valid_uuid(self) -> None:
        uuid.UUID(self.adapted["record_id"])  # raises if invalid

    def test_function_name_clean_name_unchanged(self) -> None:
        self.assertEqual(self.adapted["function_name"], "my-lambda")

    def test_adapter_version_in_provenance_chain(self) -> None:
        self.assertEqual(
            self.adapted["provenance_chain"]["adapter_version"], ADAPTER_VERSION
        )

    def test_source_layer_in_provenance_chain(self) -> None:
        self.assertEqual(
            self.adapted["provenance_chain"]["source_layer"], "layer_0"
        )

    def test_output_dict_is_json_serialisable(self) -> None:
        import json
        json.dumps(self.adapted)  # must not raise


# ---------------------------------------------------------------------------
# Test: anomaly-type normalisation
# ---------------------------------------------------------------------------

class TestAnomalyTypeNormalisation(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = RCoreToLayer1Adapter()

    def _adapt(self, anomaly: AnomalyType) -> str:
        return self.adapter.adapt(_make_record(anomaly_type=anomaly))["anomaly_type"]

    def test_benign_maps_to_benign(self) -> None:
        self.assertEqual(self._adapt(AnomalyType.BENIGN), "benign")

    def test_cpu_burst_maps_to_suspicious(self) -> None:
        self.assertEqual(self._adapt(AnomalyType.CPU_BURST), "suspicious")

    def test_memory_spike_maps_to_suspicious(self) -> None:
        self.assertEqual(self._adapt(AnomalyType.MEMORY_SPIKE), "suspicious")

    def test_adversarial_injection_maps_to_malicious(self) -> None:
        self.assertEqual(self._adapt(AnomalyType.ADVERSARIAL_INJECTION), "malicious")

    def test_data_exfiltration_maps_to_malicious(self) -> None:
        self.assertEqual(self._adapt(AnomalyType.DATA_EXFILTRATION), "malicious")

    def test_all_anomaly_types_map_to_l1_allowed_set(self) -> None:
        allowed = {"benign", "suspicious", "malicious", "unknown"}
        for a in AnomalyType:
            result = self._adapt(a)
            self.assertIn(result, allowed,
                          f"{a} → '{result}' is not in the L1 allowed set")


# ---------------------------------------------------------------------------
# Test: execution-phase normalisation
# ---------------------------------------------------------------------------

class TestExecutionPhaseNormalisation(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = RCoreToLayer1Adapter()

    def _adapt(self, phase: ExecutionPhase) -> str:
        return self.adapter.adapt(_make_record(execution_phase=phase))["execution_phase"]

    def test_invoke_maps_to_execution(self) -> None:
        self.assertEqual(self._adapt(ExecutionPhase.INVOKE), "execution")

    def test_init_maps_to_initialization(self) -> None:
        self.assertEqual(self._adapt(ExecutionPhase.INIT), "initialization")

    def test_shutdown_maps_to_completion(self) -> None:
        self.assertEqual(self._adapt(ExecutionPhase.SHUTDOWN), "completion")

    def test_all_phases_map_to_l1_allowed_set(self) -> None:
        allowed = {"initialization", "execution", "completion", "error", "timeout"}
        for p in ExecutionPhase:
            result = self._adapt(p)
            self.assertIn(result, allowed,
                          f"{p} → '{result}' is not in the L1 allowed set")


# ---------------------------------------------------------------------------
# Test: error-phase handling
# ---------------------------------------------------------------------------

class TestErrorPhaseHandling(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = RCoreToLayer1Adapter()

    def test_error_phase_adds_error_message_key(self) -> None:
        adapted = self.adapter.adapt(
            _make_record(execution_phase=ExecutionPhase.ERROR,
                         anomaly_type=AnomalyType.EXECUTION_FAILURE)
        )
        self.assertIn("error_message", adapted)

    def test_error_phase_adds_error_stack_key(self) -> None:
        adapted = self.adapter.adapt(_make_record(execution_phase=ExecutionPhase.ERROR))
        self.assertIn("error_stack", adapted)

    def test_error_stack_equals_placeholder(self) -> None:
        adapted = self.adapter.adapt(_make_record(execution_phase=ExecutionPhase.ERROR))
        self.assertEqual(adapted["error_stack"], ERROR_STACK_PLACEHOLDER)

    def test_non_error_phase_has_no_error_stack(self) -> None:
        adapted = self.adapter.adapt(_make_record(execution_phase=ExecutionPhase.INVOKE))
        self.assertNotIn("error_stack", adapted)


# ---------------------------------------------------------------------------
# Test: function-name sanitisation
# ---------------------------------------------------------------------------

class TestFunctionNameSanitisation(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = RCoreToLayer1Adapter()

    def _fn(self, function_id: str) -> str:
        return self.adapter.adapt(_make_record(function_id=function_id))["function_name"]

    def test_clean_name_is_unchanged(self) -> None:
        self.assertEqual(self._fn("my-lambda_v2.1"), "my-lambda_v2.1")

    def test_spaces_replaced_with_underscores(self) -> None:
        self.assertNotIn(" ", self._fn("my lambda"))

    def test_exclamation_mark_replaced(self) -> None:
        self.assertNotIn("\!", self._fn("bad\!name"))


    def test_long_name_truncated_at_256_chars(self) -> None:
        self.assertLessEqual(len(self._fn("a" * 300)), 256)


# ---------------------------------------------------------------------------
# Test: record-id handling
# ---------------------------------------------------------------------------

class TestRecordIdHandling(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = RCoreToLayer1Adapter()

    def test_valid_uuid_event_id_is_preserved(self) -> None:
        valid_id = str(uuid.uuid4())
        adapted = self.adapter.adapt(_make_record(event_id=valid_id))
        self.assertEqual(adapted["record_id"], valid_id)

    def test_invalid_event_id_replaced_with_new_valid_uuid(self) -> None:
        adapted = self.adapter.adapt(_make_record(event_id="not-a-uuid"))
        self.assertNotEqual(adapted["record_id"], "not-a-uuid")
        uuid.UUID(adapted["record_id"])  # must parse as valid UUID


# ---------------------------------------------------------------------------
# Test: guard conditions
# ---------------------------------------------------------------------------

class TestAdapterGuards(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = RCoreToLayer1Adapter()

    def test_none_input_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.adapter.adapt(None)  # type: ignore[arg-type]

    def test_dict_input_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.adapter.adapt({"event_id": "x"})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test: telemetry_data block
# ---------------------------------------------------------------------------

class TestTelemetryDataBlock(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = RCoreToLayer1Adapter()
        record = _make_record(duration=250.0, cpu_utilization=0.85)
        self.td = self.adapter.adapt(record)["telemetry_data"]

    def test_l0_duration_ms_correct(self) -> None:
        self.assertEqual(self.td["l0_duration_ms"], 250.0)

    def test_l0_cpu_utilization_correct(self) -> None:
        self.assertAlmostEqual(self.td["l0_cpu_utilization"], 0.85)

    def test_layer0_metrics_sub_block_present(self) -> None:
        self.assertIn("layer0_metrics", self.td)

    def test_adapter_version_in_layer0_metrics(self) -> None:
        self.assertEqual(
            self.td["layer0_metrics"]["l0_adapter_version"], ADAPTER_VERSION
        )

    def test_processing_timestamp_in_layer0_metrics(self) -> None:
        self.assertIn("l0_processing_timestamp", self.td["layer0_metrics"])


if __name__ == "__main__":
    unittest.main()
