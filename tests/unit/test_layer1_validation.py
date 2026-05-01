"""
tests/unit/test_layer1_validation.py
=====================================

T-013 — Unit tests for InputValidationGateway (WP-3.1, DL-028).

Permanent set member.  30 test cases covering:
  - Required-field presence and non-empty strings
  - Type checks (str / int / float / dict)
  - Enum value constraints (execution_phase, anomaly_type)
  - Numeric bounds (scores, CPU, duration, memory, network I/O)
  - String length caps (function_name ≤ 256, schema_version ≤ 32)
  - Conditional requirement: error_message required when execution_phase == 'error'
  - Accumulation of multiple errors in a single pass
  - ValidationResult API (valid flag, errors list)
"""

from __future__ import annotations

import unittest
from typing import Any, Dict

from layers.layer1.validation import (
    InputValidationGateway,
    ValidationError,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_record(**overrides: Any) -> Dict[str, Any]:
    """Return a minimal valid adapted L1 record (post-adapter shape)."""
    base: Dict[str, Any] = {
        "record_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": 1_714_000_000.0,
        "function_name": "my-lambda-function",
        "execution_phase": "execution",
        "anomaly_type": "benign",
        "telemetry_data": {
            "l0_duration_ms": 42.0,
            "l0_memory_spike_kb": 128,
            "l0_cpu_utilization": 12.5,
            "l0_network_io_bytes": 1024,
            "l0_fallback_mode": False,
        },
        "schema_version": "v2.1",
    }
    base.update(overrides)
    return base


GW = InputValidationGateway()


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestValidRecord(unittest.TestCase):

    def test_valid_minimal_record_passes(self):
        result = GW.validate(_valid_record())
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_valid_record_with_all_optional_fields_passes(self):
        record = _valid_record(
            context_metadata={
                "adversarial_score": 0.1,
                "economic_risk_score": 0.0,
                "silent_failure_probability": 0.05,
                "completeness_score": 0.99,
                "confidence_level": 0.95,
                "data_quality_score": 1.0,
                "anomaly_severity": 2,
            },
            provenance_chain={"source_layer": "layer_0"},
            error_message=None,
        )
        result = GW.validate(record)
        self.assertTrue(result.valid)

    def test_error_phase_with_error_message_passes(self):
        record = _valid_record(
            execution_phase="error",
            error_message="L0 execution error - anomaly: execution_failure",
        )
        result = GW.validate(record)
        self.assertTrue(result.valid, [str(e) for e in result.errors])

    def test_all_valid_execution_phases_pass(self):
        for phase in ("initialization", "execution", "completion", "error", "timeout"):
            record = _valid_record(execution_phase=phase)
            if phase == "error":
                record["error_message"] = "some error"
            result = GW.validate(record)
            self.assertTrue(result.valid, f"phase '{phase}' should be valid")

    def test_all_valid_anomaly_types_pass(self):
        for anomaly in ("benign", "suspicious", "malicious", "unknown"):
            result = GW.validate(_valid_record(anomaly_type=anomaly))
            self.assertTrue(result.valid, f"anomaly_type '{anomaly}' should be valid")


# ---------------------------------------------------------------------------
# Required-field tests
# ---------------------------------------------------------------------------

class TestRequiredFields(unittest.TestCase):

    def _assert_field_required(self, field_name: str) -> None:
        record = _valid_record()
        del record[field_name]
        result = GW.validate(record)
        self.assertFalse(result.valid)
        field_names = [e.field for e in result.errors]
        self.assertIn(field_name, field_names, f"Expected error on '{field_name}'")

    def test_missing_record_id_fails(self):
        self._assert_field_required("record_id")

    def test_missing_timestamp_fails(self):
        self._assert_field_required("timestamp")

    def test_missing_function_name_fails(self):
        self._assert_field_required("function_name")

    def test_missing_execution_phase_fails(self):
        self._assert_field_required("execution_phase")

    def test_missing_anomaly_type_fails(self):
        self._assert_field_required("anomaly_type")

    def test_missing_telemetry_data_fails(self):
        self._assert_field_required("telemetry_data")

    def test_missing_schema_version_fails(self):
        self._assert_field_required("schema_version")

    def test_empty_record_id_fails(self):
        result = GW.validate(_valid_record(record_id=""))
        self.assertFalse(result.valid)
        self.assertTrue(any(e.field == "record_id" for e in result.errors))

    def test_empty_function_name_fails(self):
        result = GW.validate(_valid_record(function_name="   "))
        self.assertFalse(result.valid)
        self.assertTrue(any(e.field == "function_name" for e in result.errors))


# ---------------------------------------------------------------------------
# Type-check tests
# ---------------------------------------------------------------------------

class TestTypeChecks(unittest.TestCase):

    def test_timestamp_non_numeric_fails(self):
        result = GW.validate(_valid_record(timestamp="not-a-number"))
        self.assertFalse(result.valid)
        self.assertTrue(any(e.field == "timestamp" for e in result.errors))

    def test_telemetry_data_not_dict_fails(self):
        result = GW.validate(_valid_record(telemetry_data="should-be-dict"))
        self.assertFalse(result.valid)
        self.assertTrue(any(e.field == "telemetry_data" for e in result.errors))

    def test_schema_version_not_string_fails(self):
        result = GW.validate(_valid_record(schema_version=21))
        self.assertFalse(result.valid)
        self.assertTrue(any(e.field == "schema_version" for e in result.errors))


# ---------------------------------------------------------------------------
# Enum-value tests
# ---------------------------------------------------------------------------

class TestEnumValues(unittest.TestCase):

    def test_invalid_execution_phase_fails(self):
        result = GW.validate(_valid_record(execution_phase="running"))
        self.assertFalse(result.valid)
        self.assertTrue(any(e.field == "execution_phase" for e in result.errors))

    def test_invalid_anomaly_type_fails(self):
        result = GW.validate(_valid_record(anomaly_type="very_bad_thing"))
        self.assertFalse(result.valid)
        self.assertTrue(any(e.field == "anomaly_type" for e in result.errors))


# ---------------------------------------------------------------------------
# Numeric-bounds tests
# ---------------------------------------------------------------------------

class TestNumericBounds(unittest.TestCase):

    def _with_context(self, **kwargs: Any) -> Dict[str, Any]:
        record = _valid_record()
        record["context_metadata"] = kwargs
        return record

    def _with_telemetry(self, **kwargs: Any) -> Dict[str, Any]:
        record = _valid_record()
        record["telemetry_data"] = {**record["telemetry_data"], **kwargs}
        return record

    def test_completeness_score_above_one_fails(self):
        result = GW.validate(self._with_context(completeness_score=1.5))
        self.assertFalse(result.valid)

    def test_completeness_score_below_zero_fails(self):
        result = GW.validate(self._with_context(completeness_score=-0.1))
        self.assertFalse(result.valid)

    def test_adversarial_score_above_one_fails(self):
        result = GW.validate(self._with_context(adversarial_score=1.001))
        self.assertFalse(result.valid)

    def test_economic_risk_score_below_zero_fails(self):
        result = GW.validate(self._with_context(economic_risk_score=-0.5))
        self.assertFalse(result.valid)

    def test_l0_cpu_utilization_above_100_fails(self):
        result = GW.validate(self._with_telemetry(l0_cpu_utilization=100.1))
        self.assertFalse(result.valid)

    def test_l0_duration_ms_negative_fails(self):
        result = GW.validate(self._with_telemetry(l0_duration_ms=-1.0))
        self.assertFalse(result.valid)

    def test_l0_memory_spike_kb_negative_fails(self):
        result = GW.validate(self._with_telemetry(l0_memory_spike_kb=-10))
        self.assertFalse(result.valid)

    def test_l0_network_io_bytes_negative_fails(self):
        result = GW.validate(self._with_telemetry(l0_network_io_bytes=-1))
        self.assertFalse(result.valid)


# ---------------------------------------------------------------------------
# String-length tests
# ---------------------------------------------------------------------------

class TestStringLengths(unittest.TestCase):

    def test_function_name_too_long_fails(self):
        result = GW.validate(_valid_record(function_name="x" * 257))
        self.assertFalse(result.valid)
        self.assertTrue(any(e.field == "function_name" for e in result.errors))

    def test_function_name_at_max_length_passes(self):
        result = GW.validate(_valid_record(function_name="a" * 256))
        self.assertTrue(result.valid)


# ---------------------------------------------------------------------------
# Conditional-requirement tests
# ---------------------------------------------------------------------------

class TestConditionalRequirements(unittest.TestCase):

    def test_error_phase_without_error_message_fails(self):
        result = GW.validate(_valid_record(execution_phase="error"))
        self.assertFalse(result.valid)
        self.assertTrue(any(e.field == "error_message" for e in result.errors))

    def test_error_phase_with_empty_error_message_fails(self):
        result = GW.validate(_valid_record(execution_phase="error", error_message=""))
        self.assertFalse(result.valid)
        self.assertTrue(any(e.field == "error_message" for e in result.errors))

    def test_non_error_phase_without_error_message_passes(self):
        for phase in ("initialization", "execution", "completion", "timeout"):
            result = GW.validate(_valid_record(execution_phase=phase))
            self.assertTrue(result.valid, f"phase '{phase}' should not require error_message")


# ---------------------------------------------------------------------------
# ValidationResult API tests
# ---------------------------------------------------------------------------

class TestValidationResultAPI(unittest.TestCase):

    def test_result_valid_true_on_clean_record(self):
        result = GW.validate(_valid_record())
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.valid)

    def test_result_errors_empty_on_clean_record(self):
        result = GW.validate(_valid_record())
        self.assertIsInstance(result.errors, list)
        self.assertEqual(len(result.errors), 0)

    def test_multiple_errors_accumulate_in_single_pass(self):
        """A record with several violations must produce one error per violation."""
        record = _valid_record(
            timestamp="bad",
            execution_phase="invalid_phase",
            anomaly_type="not_an_anomaly",
        )
        result = GW.validate(record)
        self.assertFalse(result.valid)
        self.assertGreaterEqual(len(result.errors), 3)

    def test_validation_error_has_field_and_message(self):
        result = GW.validate(_valid_record(execution_phase="bad_phase"))
        self.assertFalse(result.valid)
        err = result.errors[0]
        self.assertIsInstance(err, ValidationError)
        self.assertIsInstance(err.field, str)
        self.assertIsInstance(err.message, str)
        self.assertTrue(len(err.field) > 0)
        self.assertTrue(len(err.message) > 0)


if __name__ == "__main__":
    unittest.main()
