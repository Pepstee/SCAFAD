"""
tests/formal/test_completeness_score.py
=======================================

T-028 -- FormalVerificationEngine.compute_completeness_score unit tests.

Verifies the contract of the renamed method (WP-4.3, R-10):
  - Empty trace returns overall_score=0.0, verified=False.
  - Fully-populated trace returns overall_score=1.0, verified=True, no issues.
  - Partially-populated trace scores the correct fraction and lists missing fields.
  - overall_score >= 0.8 threshold governs the 'verified' flag.
  - Return dict always contains exactly the keys: overall_score, verified, issues.

Run from repo root:
    python3 tests/formal/test_completeness_score.py
    python3 -m pytest tests/formal/test_completeness_score.py

DL-037 | WP-4.3
"""
from __future__ import annotations

import asyncio
import sys
import os
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from app_formal import FormalVerificationEngine
from app_config import FormalVerificationConfig


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


_REQUIRED_FIELDS = [
    "event_id", "timestamp", "function_id", "execution_phase",
    "anomaly_type", "duration", "memory_spike_kb", "cpu_utilization",
    "network_io_bytes", "source",
]


def _full_record(**overrides):
    base = {
        "event_id":         "ev-001",
        "timestamp":        1_700_000_000.0,
        "function_id":      "fn-test",
        "execution_phase":  "INVOKE",
        "anomaly_type":     "BENIGN",
        "duration":         0.120,
        "memory_spike_kb":  65536,
        "cpu_utilization":  15.0,
        "network_io_bytes": 1024,
        "source":           "SCAFAD_LAYER0",
    }
    base.update(overrides)
    return base


class TestCompletenessScoreEmpty(unittest.TestCase):

    def setUp(self):
        self.engine = FormalVerificationEngine(FormalVerificationConfig())

    def test_empty_trace_returns_zero_score(self):
        result = _run(self.engine.compute_completeness_score([]))
        self.assertEqual(result["overall_score"], 0.0)

    def test_empty_trace_not_verified(self):
        result = _run(self.engine.compute_completeness_score([]))
        self.assertFalse(result["verified"])

    def test_empty_trace_has_issue_flag(self):
        result = _run(self.engine.compute_completeness_score([]))
        self.assertIn("empty_telemetry_trace", result["issues"])

    def test_return_keys_present_on_empty(self):
        result = _run(self.engine.compute_completeness_score([]))
        for key in ("overall_score", "verified", "issues"):
            self.assertIn(key, result, "Missing key: %s" % key)


class TestCompletenessScoreFullRecord(unittest.TestCase):

    def setUp(self):
        self.engine = FormalVerificationEngine(FormalVerificationConfig())

    def test_full_record_scores_one(self):
        result = _run(self.engine.compute_completeness_score([_full_record()]))
        self.assertAlmostEqual(result["overall_score"], 1.0)

    def test_full_record_is_verified(self):
        result = _run(self.engine.compute_completeness_score([_full_record()]))
        self.assertTrue(result["verified"])

    def test_full_record_no_issues(self):
        result = _run(self.engine.compute_completeness_score([_full_record()]))
        self.assertEqual(result["issues"], [])

    def test_multiple_full_records_score_one(self):
        records = [_full_record(event_id="ev-%03d" % i) for i in range(10)]
        result = _run(self.engine.compute_completeness_score(records))
        self.assertAlmostEqual(result["overall_score"], 1.0)


class TestCompletenessScorePartial(unittest.TestCase):

    def setUp(self):
        self.engine = FormalVerificationEngine(FormalVerificationConfig())

    def test_half_fields_present_scores_half(self):
        record = _full_record()
        for field in _REQUIRED_FIELDS[5:]:
            record[field] = None
        result = _run(self.engine.compute_completeness_score([record]))
        self.assertAlmostEqual(result["overall_score"], 0.5, places=5)

    def test_partial_record_not_verified(self):
        record = _full_record()
        for field in _REQUIRED_FIELDS[5:]:
            record[field] = None
        result = _run(self.engine.compute_completeness_score([record]))
        self.assertFalse(result["verified"])

    def test_partial_record_lists_missing_fields(self):
        record = _full_record()
        record["duration"] = None
        record["source"] = None
        result = _run(self.engine.compute_completeness_score([record]))
        self.assertEqual(len(result["issues"]), 1)
        missing = result["issues"][0]["missing_fields"]
        self.assertIn("duration", missing)
        self.assertIn("source", missing)

    def test_issue_contains_record_index(self):
        records = [_full_record(), _full_record(duration=None)]
        result = _run(self.engine.compute_completeness_score(records))
        indices = [issue["record_index"] for issue in result["issues"]]
        self.assertIn(1, indices)

    def test_mixed_records_score_is_mean(self):
        records = [_full_record(), _full_record(duration=None)]
        result = _run(self.engine.compute_completeness_score(records))
        self.assertAlmostEqual(result["overall_score"], (1.0 + 0.9) / 2, places=5)


class TestCompletenessScoreThreshold(unittest.TestCase):

    def setUp(self):
        self.engine = FormalVerificationEngine(FormalVerificationConfig())

    def test_score_08_is_verified(self):
        record = _full_record()
        for field in _REQUIRED_FIELDS[8:]:
            record[field] = None
        result = _run(self.engine.compute_completeness_score([record]))
        self.assertAlmostEqual(result["overall_score"], 0.8, places=5)
        self.assertTrue(result["verified"])

    def test_score_below_08_not_verified(self):
        record = _full_record()
        for field in _REQUIRED_FIELDS[7:]:
            record[field] = None
        result = _run(self.engine.compute_completeness_score([record]))
        self.assertAlmostEqual(result["overall_score"], 0.7, places=5)
        self.assertFalse(result["verified"])

    def test_overall_score_is_float(self):
        result = _run(self.engine.compute_completeness_score([_full_record()]))
        self.assertIsInstance(result["overall_score"], float)

    def test_overall_score_bounded(self):
        result = _run(self.engine.compute_completeness_score([_full_record()]))
        self.assertGreaterEqual(result["overall_score"], 0.0)
        self.assertLessEqual(result["overall_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
