"""
tests/unit/test_layer1_preservation.py
=======================================

T-014 — Unit tests for preservation scoring (WP-3.2, DL-029).

Permanent set member.  30 test cases covering:
  - All critical fields preserved  → score = 1.0
  - All critical fields lost       → score = 0.0
  - Partial preservation           → score in (0, 1)
  - Numeric within epsilon (1e-9)  → preserved
  - Numeric beyond epsilon         → at risk
  - Boolean identity               → preserved / at risk
  - String (enum) identity         → preserved / at risk
  - Nested telemetry_data fields   → scored
  - Nested context_metadata fields → scored
  - Extra non-critical fields changed → no effect on score
  - Field missing from processed   → at risk
  - Malformed / non-dict input     → fail-open (score=0, recommendation)
  - CRITICAL_FIELDS constant       → correct membership
  - PreservationAssessment API     → dataclass shape, to_dict presence
"""

from __future__ import annotations

import math
import unittest
from typing import Any, Dict

from layers.layer1.preservation import (
    CRITICAL_FIELDS,
    PreservationAssessment,
    assess_preservation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_record(**overrides: Any) -> Dict[str, Any]:
    """Minimal adapted L1 record with all critical fields populated."""
    base: Dict[str, Any] = {
        "record_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": 1_714_000_000.0,
        "function_name": "my-lambda",
        "execution_phase": "execution",
        "anomaly_type": "benign",
        "schema_version": "v2.1",
        "telemetry_data": {
            "l0_duration_ms": 42.0,
            "l0_memory_spike_kb": 128,
            "l0_cpu_utilization": 12.5,
            "l0_network_io_bytes": 1024,
            "l0_fallback_mode": False,
        },
        "context_metadata": {
            "adversarial_score": 0.05,
            "economic_risk_score": 0.10,
        },
        "provenance_chain": {},
    }
    base.update(overrides)
    return base


import copy


def _processed_copy(original: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(original)


# ---------------------------------------------------------------------------
# CRITICAL_FIELDS membership tests
# ---------------------------------------------------------------------------

class TestCriticalFieldsConstant(unittest.TestCase):

    def test_execution_phase_is_critical(self):
        self.assertIn("execution_phase", CRITICAL_FIELDS)

    def test_anomaly_type_is_critical(self):
        self.assertIn("anomaly_type", CRITICAL_FIELDS)

    def test_l0_duration_ms_is_critical(self):
        self.assertIn("telemetry_data.l0_duration_ms", CRITICAL_FIELDS)

    def test_l0_memory_spike_kb_is_critical(self):
        self.assertIn("telemetry_data.l0_memory_spike_kb", CRITICAL_FIELDS)

    def test_l0_cpu_utilization_is_critical(self):
        self.assertIn("telemetry_data.l0_cpu_utilization", CRITICAL_FIELDS)

    def test_l0_network_io_bytes_is_critical(self):
        self.assertIn("telemetry_data.l0_network_io_bytes", CRITICAL_FIELDS)

    def test_l0_fallback_mode_is_critical(self):
        self.assertIn("telemetry_data.l0_fallback_mode", CRITICAL_FIELDS)

    def test_adversarial_score_is_critical(self):
        self.assertIn("context_metadata.adversarial_score", CRITICAL_FIELDS)

    def test_economic_risk_score_is_critical(self):
        self.assertIn("context_metadata.economic_risk_score", CRITICAL_FIELDS)


# ---------------------------------------------------------------------------
# PreservationAssessment API
# ---------------------------------------------------------------------------

class TestPreservationAssessmentAPI(unittest.TestCase):

    def test_has_preservation_score(self):
        a = assess_preservation(_base_record(), _base_record())
        self.assertIsInstance(a.preservation_score, float)

    def test_has_at_risk_fields(self):
        a = assess_preservation(_base_record(), _base_record())
        self.assertIsInstance(a.at_risk_fields, list)

    def test_has_recommendations(self):
        a = assess_preservation(_base_record(), _base_record())
        self.assertIsInstance(a.recommendations, list)

    def test_score_bounded_0_1(self):
        a = assess_preservation(_base_record(), _base_record())
        self.assertGreaterEqual(a.preservation_score, 0.0)
        self.assertLessEqual(a.preservation_score, 1.0)


# ---------------------------------------------------------------------------
# Happy-path: all critical fields preserved
# ---------------------------------------------------------------------------

class TestAllPreserved(unittest.TestCase):

    def test_identical_records_score_one(self):
        rec = _base_record()
        result = assess_preservation(rec, _processed_copy(rec))
        self.assertAlmostEqual(result.preservation_score, 1.0, places=9)

    def test_identical_records_no_at_risk_fields(self):
        rec = _base_record()
        result = assess_preservation(rec, _processed_copy(rec))
        self.assertEqual(result.at_risk_fields, [])

    def test_non_critical_field_change_does_not_affect_score(self):
        original = _base_record()
        processed = _processed_copy(original)
        processed["record_id"] = "different-id"
        processed["schema_version"] = "v9.9"
        result = assess_preservation(original, processed)
        self.assertAlmostEqual(result.preservation_score, 1.0, places=9)


# ---------------------------------------------------------------------------
# All critical fields lost
# ---------------------------------------------------------------------------

class TestAllLost(unittest.TestCase):

    def test_empty_processed_scores_zero(self):
        original = _base_record()
        result = assess_preservation(original, {})
        self.assertAlmostEqual(result.preservation_score, 0.0, places=9)

    def test_empty_processed_all_critical_at_risk(self):
        original = _base_record()
        result = assess_preservation(original, {})
        for field in CRITICAL_FIELDS:
            self.assertIn(field, result.at_risk_fields)


# ---------------------------------------------------------------------------
# Partial preservation
# ---------------------------------------------------------------------------

class TestPartialPreservation(unittest.TestCase):

    def test_one_field_changed_score_below_one(self):
        original = _base_record()
        processed = _processed_copy(original)
        processed["anomaly_type"] = "suspicious"
        result = assess_preservation(original, processed)
        self.assertLess(result.preservation_score, 1.0)
        self.assertGreater(result.preservation_score, 0.0)

    def test_changed_field_appears_in_at_risk(self):
        original = _base_record()
        processed = _processed_copy(original)
        processed["execution_phase"] = "error"
        result = assess_preservation(original, processed)
        self.assertIn("execution_phase", result.at_risk_fields)

    def test_unchanged_critical_fields_not_at_risk(self):
        original = _base_record()
        processed = _processed_copy(original)
        processed["anomaly_type"] = "malicious"
        result = assess_preservation(original, processed)
        self.assertNotIn("execution_phase", result.at_risk_fields)

    def test_score_is_fraction_of_preserved(self):
        """Change exactly 1 of N critical fields → score = (N-1)/N."""
        original = _base_record()
        processed = _processed_copy(original)
        processed["anomaly_type"] = "malicious"
        n = len(CRITICAL_FIELDS)
        result = assess_preservation(original, processed)
        expected = (n - 1) / n
        self.assertAlmostEqual(result.preservation_score, expected, places=4)


# ---------------------------------------------------------------------------
# Numeric epsilon tests
# ---------------------------------------------------------------------------

class TestNumericEpsilon(unittest.TestCase):

    def test_numeric_within_epsilon_preserved(self):
        original = _base_record()
        processed = _processed_copy(original)
        # Perturb by less than 1e-9
        processed["telemetry_data"]["l0_duration_ms"] = 42.0 + 1e-10
        result = assess_preservation(original, processed)
        self.assertNotIn("telemetry_data.l0_duration_ms", result.at_risk_fields)

    def test_numeric_beyond_epsilon_at_risk(self):
        original = _base_record()
        processed = _processed_copy(original)
        processed["telemetry_data"]["l0_duration_ms"] = 42.0 + 1e-8
        result = assess_preservation(original, processed)
        self.assertIn("telemetry_data.l0_duration_ms", result.at_risk_fields)

    def test_integer_field_exact_match_preserved(self):
        original = _base_record()
        processed = _processed_copy(original)
        # l0_memory_spike_kb is int; same value
        result = assess_preservation(original, processed)
        self.assertNotIn("telemetry_data.l0_memory_spike_kb", result.at_risk_fields)

    def test_integer_field_changed_at_risk(self):
        original = _base_record()
        processed = _processed_copy(original)
        processed["telemetry_data"]["l0_memory_spike_kb"] = 999
        result = assess_preservation(original, processed)
        self.assertIn("telemetry_data.l0_memory_spike_kb", result.at_risk_fields)


# ---------------------------------------------------------------------------
# Boolean field tests
# ---------------------------------------------------------------------------

class TestBooleanFields(unittest.TestCase):

    def test_bool_unchanged_preserved(self):
        original = _base_record()
        processed = _processed_copy(original)
        result = assess_preservation(original, processed)
        self.assertNotIn("telemetry_data.l0_fallback_mode", result.at_risk_fields)

    def test_bool_changed_at_risk(self):
        original = _base_record()
        processed = _processed_copy(original)
        processed["telemetry_data"]["l0_fallback_mode"] = True
        result = assess_preservation(original, processed)
        self.assertIn("telemetry_data.l0_fallback_mode", result.at_risk_fields)


# ---------------------------------------------------------------------------
# Nested field tests
# ---------------------------------------------------------------------------

class TestNestedFields(unittest.TestCase):

    def test_adversarial_score_preserved_when_unchanged(self):
        original = _base_record()
        processed = _processed_copy(original)
        result = assess_preservation(original, processed)
        self.assertNotIn("context_metadata.adversarial_score", result.at_risk_fields)

    def test_adversarial_score_at_risk_when_changed(self):
        original = _base_record()
        processed = _processed_copy(original)
        processed["context_metadata"]["adversarial_score"] = 0.99
        result = assess_preservation(original, processed)
        self.assertIn("context_metadata.adversarial_score", result.at_risk_fields)

    def test_economic_risk_score_at_risk_when_changed(self):
        original = _base_record()
        processed = _processed_copy(original)
        processed["context_metadata"]["economic_risk_score"] = 0.95
        result = assess_preservation(original, processed)
        self.assertIn("context_metadata.economic_risk_score", result.at_risk_fields)

    def test_missing_telemetry_data_section_marks_fields_at_risk(self):
        original = _base_record()
        processed = _processed_copy(original)
        del processed["telemetry_data"]
        result = assess_preservation(original, processed)
        self.assertIn("telemetry_data.l0_duration_ms", result.at_risk_fields)

    def test_missing_context_metadata_section_marks_fields_at_risk(self):
        original = _base_record()
        processed = _processed_copy(original)
        del processed["context_metadata"]
        result = assess_preservation(original, processed)
        self.assertIn("context_metadata.adversarial_score", result.at_risk_fields)


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class TestRecommendations(unittest.TestCase):

    def test_no_recommendations_when_all_preserved(self):
        rec = _base_record()
        result = assess_preservation(rec, _processed_copy(rec))
        self.assertEqual(result.recommendations, [])

    def test_recommendations_populated_when_at_risk(self):
        original = _base_record()
        processed = _processed_copy(original)
        processed["anomaly_type"] = "malicious"
        result = assess_preservation(original, processed)
        self.assertGreater(len(result.recommendations), 0)


# ---------------------------------------------------------------------------
# Fail-open: malformed input
# ---------------------------------------------------------------------------

class TestFailOpen(unittest.TestCase):

    def test_none_original_returns_zero_score(self):
        result = assess_preservation(None, _base_record())  # type: ignore[arg-type]
        self.assertAlmostEqual(result.preservation_score, 0.0, places=9)

    def test_none_original_has_recommendation(self):
        result = assess_preservation(None, _base_record())  # type: ignore[arg-type]
        self.assertGreater(len(result.recommendations), 0)

    def test_non_dict_processed_returns_zero_score(self):
        result = assess_preservation(_base_record(), "not-a-dict")  # type: ignore[arg-type]
        self.assertAlmostEqual(result.preservation_score, 0.0, places=9)

    def test_both_empty_dicts_returns_zero_score(self):
        # No critical fields in either → nothing to score; fail-open to 0
        result = assess_preservation({}, {})
        self.assertAlmostEqual(result.preservation_score, 0.0, places=9)


if __name__ == "__main__":
    unittest.main()
