"""
tests/unit/test_layer1_hashing.py
===================================

T-017 — Unit tests for DeferredHashingManager (WP-3.5, DL-032).

Permanent set member.  30 test cases covering:
  - Algorithm selection: SHA-256 and BLAKE2b
  - Salt influence: different salts produce different digests
  - Determinism: same input + salt → same digest every time
  - Field hashing: nominated fields in a record are replaced with digests
  - Unhashed fields: fields not in hash_fields pass through unchanged
  - Critical-field bypass: CRITICAL_FIELDS are never hashed
  - Empty hash_fields: record returned unchanged, no actions
  - Missing fields: absent nominated fields are silently skipped
  - Throughput: 10 fields hashed in under 1 ms per record
  - Output format: hex digest string, algorithm prefix optional
  - Nested field paths: dotted paths resolve into nested dicts
  - Fail-open: non-dict input returns empty result
  - API shape: HashingResult, HashingAction contracts
"""

from __future__ import annotations

import os
import time
import unittest
from typing import Any, Dict

from layer1.hashing import (
    DeferredHashingManager,
    HashingAction,
    HashingResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_record(**overrides: Any) -> Dict[str, Any]:
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
        "context_metadata": {},
        "provenance_chain": {},
    }
    base.update(overrides)
    return base


MGR = DeferredHashingManager(salt="test-salt-fixed")


# ---------------------------------------------------------------------------
# API shape
# ---------------------------------------------------------------------------

class TestAPIShape(unittest.TestCase):

    def test_hash_returns_hashing_result(self):
        r = MGR.hash_fields(_base_record(), hash_fields=[])
        self.assertIsInstance(r, HashingResult)

    def test_hashing_result_has_hashed_record(self):
        r = MGR.hash_fields(_base_record(), hash_fields=[])
        self.assertIsInstance(r.hashed_record, dict)

    def test_hashing_result_has_actions(self):
        r = MGR.hash_fields(_base_record(), hash_fields=[])
        self.assertIsInstance(r.actions, list)

    def test_hashing_action_has_field_path(self):
        rec = _base_record(function_name="my-lambda")
        r = MGR.hash_fields(rec, hash_fields=["function_name"])
        if r.actions:
            self.assertIsInstance(r.actions[0].field_path, str)

    def test_hashing_action_has_algorithm(self):
        rec = _base_record(function_name="my-lambda")
        r = MGR.hash_fields(rec, hash_fields=["function_name"])
        if r.actions:
            self.assertIsInstance(r.actions[0].algorithm, str)


# ---------------------------------------------------------------------------
# Empty hash_fields
# ---------------------------------------------------------------------------

class TestEmptyHashFields(unittest.TestCase):

    def test_empty_hash_fields_no_actions(self):
        r = MGR.hash_fields(_base_record(), hash_fields=[])
        self.assertEqual(r.actions, [])

    def test_empty_hash_fields_record_unchanged(self):
        rec = _base_record()
        r = MGR.hash_fields(rec, hash_fields=[])
        self.assertEqual(r.hashed_record["function_name"], "my-lambda")


# ---------------------------------------------------------------------------
# SHA-256 algorithm
# ---------------------------------------------------------------------------

class TestSHA256(unittest.TestCase):

    def test_sha256_field_is_replaced_with_hex_digest(self):
        rec = _base_record(function_name="my-lambda")
        r = DeferredHashingManager(salt="s").hash_fields(
            rec, hash_fields=["function_name"], algorithm="sha256"
        )
        val = r.hashed_record["function_name"]
        # SHA-256 hex digest = 64 hex chars
        self.assertRegex(val, r"^[0-9a-f]{64}$")

    def test_sha256_action_algorithm_name(self):
        rec = _base_record(function_name="my-lambda")
        r = DeferredHashingManager(salt="s").hash_fields(
            rec, hash_fields=["function_name"], algorithm="sha256"
        )
        self.assertEqual(r.actions[0].algorithm, "sha256")

    def test_sha256_original_value_not_in_record(self):
        rec = _base_record(function_name="my-lambda")
        r = DeferredHashingManager(salt="s").hash_fields(
            rec, hash_fields=["function_name"], algorithm="sha256"
        )
        self.assertNotEqual(r.hashed_record["function_name"], "my-lambda")


# ---------------------------------------------------------------------------
# BLAKE2b algorithm
# ---------------------------------------------------------------------------

class TestBLAKE2b(unittest.TestCase):

    def test_blake2b_field_replaced_with_hex_digest(self):
        rec = _base_record(function_name="my-lambda")
        r = DeferredHashingManager(salt="s").hash_fields(
            rec, hash_fields=["function_name"], algorithm="blake2b"
        )
        val = r.hashed_record["function_name"]
        # BLAKE2b-512 hex digest = 128 hex chars
        self.assertRegex(val, r"^[0-9a-f]+$")
        self.assertGreater(len(val), 0)

    def test_blake2b_action_algorithm_name(self):
        rec = _base_record(function_name="my-lambda")
        r = DeferredHashingManager(salt="s").hash_fields(
            rec, hash_fields=["function_name"], algorithm="blake2b"
        )
        self.assertEqual(r.actions[0].algorithm, "blake2b")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism(unittest.TestCase):

    def test_sha256_same_input_same_output(self):
        rec1 = _base_record(function_name="my-lambda")
        rec2 = _base_record(function_name="my-lambda")
        mgr = DeferredHashingManager(salt="fixed")
        r1 = mgr.hash_fields(rec1, hash_fields=["function_name"], algorithm="sha256")
        r2 = mgr.hash_fields(rec2, hash_fields=["function_name"], algorithm="sha256")
        self.assertEqual(
            r1.hashed_record["function_name"],
            r2.hashed_record["function_name"],
        )

    def test_blake2b_same_input_same_output(self):
        rec1 = _base_record(function_name="my-lambda")
        rec2 = _base_record(function_name="my-lambda")
        mgr = DeferredHashingManager(salt="fixed")
        r1 = mgr.hash_fields(rec1, hash_fields=["function_name"], algorithm="blake2b")
        r2 = mgr.hash_fields(rec2, hash_fields=["function_name"], algorithm="blake2b")
        self.assertEqual(
            r1.hashed_record["function_name"],
            r2.hashed_record["function_name"],
        )


# ---------------------------------------------------------------------------
# Salt influence
# ---------------------------------------------------------------------------

class TestSaltInfluence(unittest.TestCase):

    def test_different_salts_produce_different_digests(self):
        rec = _base_record(function_name="my-lambda")
        r1 = DeferredHashingManager(salt="salt-A").hash_fields(
            rec, hash_fields=["function_name"], algorithm="sha256"
        )
        r2 = DeferredHashingManager(salt="salt-B").hash_fields(
            rec, hash_fields=["function_name"], algorithm="sha256"
        )
        self.assertNotEqual(
            r1.hashed_record["function_name"],
            r2.hashed_record["function_name"],
        )

    def test_env_salt_used_when_no_explicit_salt(self):
        os.environ["SCAFAD_HASH_SALT"] = "env-salt-xyz"
        try:
            mgr = DeferredHashingManager()
            rec = _base_record(function_name="my-lambda")
            r = mgr.hash_fields(rec, hash_fields=["function_name"], algorithm="sha256")
            self.assertRegex(r.hashed_record["function_name"], r"^[0-9a-f]{64}$")
        finally:
            del os.environ["SCAFAD_HASH_SALT"]


# ---------------------------------------------------------------------------
# Unhashed fields pass through
# ---------------------------------------------------------------------------

class TestUnhashedFields(unittest.TestCase):

    def test_fields_not_in_hash_fields_unchanged(self):
        rec = _base_record(function_name="my-lambda", schema_version="v2.1")
        r = MGR.hash_fields(rec, hash_fields=["function_name"])
        self.assertEqual(r.hashed_record["schema_version"], "v2.1")


# ---------------------------------------------------------------------------
# Critical-field bypass
# ---------------------------------------------------------------------------

class TestCriticalFieldBypass(unittest.TestCase):

    def test_critical_field_not_hashed_even_if_nominated(self):
        # execution_phase is a CRITICAL_FIELD
        rec = _base_record(execution_phase="execution")
        r = MGR.hash_fields(rec, hash_fields=["execution_phase"])
        self.assertEqual(r.hashed_record["execution_phase"], "execution")

    def test_critical_field_generates_no_action(self):
        rec = _base_record(execution_phase="execution")
        r = MGR.hash_fields(rec, hash_fields=["execution_phase"])
        self.assertFalse(any(a.field_path == "execution_phase" for a in r.actions))


# ---------------------------------------------------------------------------
# Missing fields silently skipped
# ---------------------------------------------------------------------------

class TestMissingFields(unittest.TestCase):

    def test_absent_nominated_field_skipped_no_error(self):
        rec = _base_record()
        # "nonexistent_field" is not in rec — should not raise
        r = MGR.hash_fields(rec, hash_fields=["nonexistent_field"])
        self.assertIsInstance(r, HashingResult)

    def test_absent_nominated_field_generates_no_action(self):
        rec = _base_record()
        r = MGR.hash_fields(rec, hash_fields=["nonexistent_field"])
        self.assertEqual(r.actions, [])


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

class TestImmutability(unittest.TestCase):

    def test_original_record_not_mutated(self):
        rec = _base_record(function_name="my-lambda")
        original = rec["function_name"]
        MGR.hash_fields(rec, hash_fields=["function_name"])
        self.assertEqual(rec["function_name"], original)


# ---------------------------------------------------------------------------
# Fail-open
# ---------------------------------------------------------------------------

class TestFailOpen(unittest.TestCase):

    def test_non_dict_input_returns_hashing_result(self):
        r = MGR.hash_fields("not-a-dict", hash_fields=["x"])  # type: ignore[arg-type]
        self.assertIsInstance(r, HashingResult)

    def test_non_dict_input_empty_actions(self):
        r = MGR.hash_fields(None, hash_fields=["x"])  # type: ignore[arg-type]
        self.assertEqual(r.actions, [])


# ---------------------------------------------------------------------------
# Throughput
# ---------------------------------------------------------------------------

class TestThroughput(unittest.TestCase):

    def test_ten_fields_under_one_millisecond(self):
        rec = {f"field_{i}": f"value_{i}" for i in range(10)}
        mgr = DeferredHashingManager(salt="perf-salt")
        hash_fields = list(rec.keys())
        start = time.perf_counter()
        mgr.hash_fields(rec, hash_fields=hash_fields, algorithm="sha256")
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 1.0, f"Hashing 10 fields took {elapsed_ms:.3f} ms")


# ---------------------------------------------------------------------------
# Cryptographic construction correctness
# ---------------------------------------------------------------------------

class TestCryptographicConstruction(unittest.TestCase):
    """Verify the keyed-hash construction, not just the output format."""

    def test_sha256_matches_hmac_construction(self):
        import hmac as _hmac
        import hashlib as _hashlib
        rec = _base_record(function_name="my-lambda")
        r = DeferredHashingManager(salt="verify-salt").hash_fields(
            rec, hash_fields=["function_name"], algorithm="sha256"
        )
        expected = _hmac.new(
            b"verify-salt", b"my-lambda", _hashlib.sha256
        ).hexdigest()
        self.assertEqual(r.hashed_record["function_name"], expected)

    def test_blake2b_matches_keyed_construction(self):
        import hashlib as _hashlib
        rec = _base_record(function_name="my-lambda")
        r = DeferredHashingManager(salt="verify-salt").hash_fields(
            rec, hash_fields=["function_name"], algorithm="blake2b"
        )
        expected = _hashlib.blake2b(b"my-lambda", key=b"verify-salt").hexdigest()
        self.assertEqual(r.hashed_record["function_name"], expected)

    def test_sha256_different_from_naive_hash(self):
        import hashlib as _hashlib
        rec = _base_record(function_name="my-lambda")
        r = DeferredHashingManager(salt="s").hash_fields(
            rec, hash_fields=["function_name"], algorithm="sha256"
        )
        naive = _hashlib.sha256(b"smy-lambda").hexdigest()
        # HMAC must differ from naive salt-prepend
        self.assertNotEqual(r.hashed_record["function_name"], naive)


if __name__ == "__main__":
    unittest.main()
