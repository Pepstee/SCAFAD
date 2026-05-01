"""
T-016 -- HMAC Signing E2E Contract Test (WP-4.9, I-6)
======================================================

Permanent contract test enforcing Invariant I-6 from
SCAFAD_MASTER_BLUEPRINT.md § 3.4:

    I-6: Every outbound L0 record carries ``signature`` and ``content_hash``,
         both verifiable with the deployment's HMAC key.

Invariants enforced
-------------------
1.  After ``sign_record()``, ``signature`` is a non-empty hex string.
2.  After ``sign_record()``, ``content_hash`` is a non-empty hex string.
3.  ``signature_algorithm`` is the literal string ``"HMAC-SHA256"``.
4.  ``verify_signature(key)`` with the **correct** key returns ``True``.
5.  ``content_hash`` is mathematically correct — SHA-256 of the canonical
    JSON payload (10 deterministic fields).
6.  ``signature`` is mathematically correct — HMAC-SHA256 keyed on the
    deployment key over the content_hash bytes.
7.  ``verify_signature(wrong_key)`` returns ``False`` (wrong-key rejection).
8.  Mutating any content field after signing invalidates the signature.
9.  An unsigned record (``sign_record()`` never called) fails verification.
10. ``content_hash`` is **deterministic**: signing the same record twice
    yields identical hashes and signatures.
11. Each distinct record produces a **distinct** content_hash (collision
    sensitivity).
12. Signing is idempotent: a second ``sign_record()`` call replaces both
    fields without error.

Decision Log
------------
DL-049: T-016 enters permanent contract set (WP-4.9, 2026-04-24).

Signing key
-----------
Tests use the fixed test key ``b'test-hmac-key-32bytes-padding!!'``
(32 bytes).  Production keys are loaded from environment / KMS; never
use a production key here.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import unittest
from copy import deepcopy
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fixed test key — 32 bytes, never used in production
# ---------------------------------------------------------------------------

_TEST_KEY: bytes = b"test-hmac-key-32bytes-padding!!"
_TEST_KEY_STR: str = _TEST_KEY.decode("utf-8")
_WRONG_KEY_STR: str = "wrong-key-completely-different!!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(**overrides: Any):
    """Return a minimal, fully-populated TelemetryRecord for testing."""
    from layer0.app_telemetry import (
        AnomalyType,
        ExecutionPhase,
        TelemetryRecord,
        TelemetrySource,
    )

    defaults = dict(
        event_id="t016-event-001",
        timestamp=1_714_000_000.0,          # fixed for determinism
        function_id="test-function-hmac",
        execution_phase=ExecutionPhase.INVOKE,
        anomaly_type=AnomalyType.BENIGN,
        duration=0.250,
        memory_spike_kb=256,
        cpu_utilization=15.0,
        network_io_bytes=1024,
        fallback_mode=False,
        source=TelemetrySource.SCAFAD_LAYER0,
        concurrency_id="conc-t016",
    )
    defaults.update(overrides)
    return TelemetryRecord(**defaults)


def _expected_content_hash(record) -> str:
    """Reproduce the content_hash independently of TelemetryRecord internals."""
    content_data = {
        "event_id":        record.event_id,
        "timestamp":       record.timestamp,
        "function_id":     record.function_id,
        "execution_phase": record.execution_phase.value,
        "anomaly_type":    record.anomaly_type.value,
        "duration":        record.duration,
        "memory_spike_kb": record.memory_spike_kb,
        "cpu_utilization": record.cpu_utilization,
        "network_io_bytes": record.network_io_bytes,
        "source":          record.source.value,
    }
    canonical_json = json.dumps(content_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _expected_hmac_signature(content_hash: str, key_str: str) -> str:
    """Reproduce the HMAC-SHA256 signature independently of TelemetryRecord internals."""
    return hmac.new(
        key_str.encode("utf-8"),
        content_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Contract tests — I-6
# ---------------------------------------------------------------------------

class TestHmacSigningPresence:
    """
    Invariants 1–3: signed records carry the required cryptographic fields.
    """

    def test_signature_field_present_after_signing(self):
        """I-6 [1]: signature field is non-None and non-empty after sign_record()."""
        record = _make_record()
        assert record.signature is None, "Pre-condition: signature must be None before signing"
        record.sign_record(_TEST_KEY_STR)
        assert record.signature is not None, "signature must be set by sign_record()"
        assert len(record.signature) > 0, "signature must be non-empty"

    def test_content_hash_field_present_after_signing(self):
        """I-6 [2]: content_hash field is non-None and non-empty after sign_record()."""
        record = _make_record()
        assert record.content_hash is None, "Pre-condition: content_hash must be None before signing"
        record.sign_record(_TEST_KEY_STR)
        assert record.content_hash is not None, "content_hash must be set by sign_record()"
        assert len(record.content_hash) > 0, "content_hash must be non-empty"

    def test_signature_algorithm_literal(self):
        """I-6 [3]: signature_algorithm must be the literal string 'HMAC-SHA256'."""
        record = _make_record()
        assert record.signature_algorithm == "HMAC-SHA256", (
            f"signature_algorithm must be 'HMAC-SHA256', got {record.signature_algorithm!r}"
        )

    def test_signature_is_hex_string(self):
        """Signature is a 64-character lowercase hex string (SHA-256 HMAC output)."""
        record = _make_record()
        record.sign_record(_TEST_KEY_STR)
        sig = record.signature
        assert isinstance(sig, str), f"signature must be str, got {type(sig)}"
        assert len(sig) == 64, f"HMAC-SHA256 hex digest must be 64 chars, got {len(sig)}"
        # Must be valid hex
        int(sig, 16)  # raises ValueError if not valid hex

    def test_content_hash_is_sha256_hex(self):
        """content_hash is a 64-character lowercase hex string (SHA-256 output)."""
        record = _make_record()
        record.sign_record(_TEST_KEY_STR)
        ch = record.content_hash
        assert isinstance(ch, str), f"content_hash must be str, got {type(ch)}"
        assert len(ch) == 64, f"SHA-256 hex digest must be 64 chars, got {len(ch)}"
        int(ch, 16)  # raises ValueError if not valid hex


class TestHmacSigningCorrectness:
    """
    Invariants 5–6: cryptographic values are mathematically correct.
    """

    def test_content_hash_matches_sha256_of_canonical_payload(self):
        """I-6 [5]: content_hash == SHA-256(canonical JSON of 10 deterministic fields)."""
        record = _make_record()
        record.sign_record(_TEST_KEY_STR)
        expected = _expected_content_hash(record)
        assert record.content_hash == expected, (
            f"content_hash mismatch.\n"
            f"  Recorded:  {record.content_hash}\n"
            f"  Expected:  {expected}"
        )

    def test_signature_matches_hmac_sha256_of_content_hash(self):
        """I-6 [6]: signature == HMAC-SHA256(key, content_hash)."""
        record = _make_record()
        record.sign_record(_TEST_KEY_STR)
        expected_sig = _expected_hmac_signature(record.content_hash, _TEST_KEY_STR)
        assert record.signature == expected_sig, (
            f"signature mismatch.\n"
            f"  Recorded:  {record.signature}\n"
            f"  Expected:  {expected_sig}"
        )

    def test_verify_signature_returns_true_with_correct_key(self):
        """I-6 [4]: verify_signature() with the correct key returns True."""
        record = _make_record()
        record.sign_record(_TEST_KEY_STR)
        assert record.verify_signature(_TEST_KEY_STR) is True, (
            "verify_signature() must return True when called with the signing key"
        )


class TestHmacSigningTamperDetection:
    """
    Invariants 7–9: tamper-detection properties of the HMAC scheme.
    """

    def test_verify_signature_fails_with_wrong_key(self):
        """I-6 [7]: verify_signature() with a different key returns False."""
        record = _make_record()
        record.sign_record(_TEST_KEY_STR)
        assert record.verify_signature(_WRONG_KEY_STR) is False, (
            "verify_signature() must return False when called with the wrong key"
        )

    def test_unsigned_record_fails_verification(self):
        """I-6 [9]: an unsigned record (sign_record() never called) fails verification."""
        record = _make_record()
        # Neither signature nor content_hash is set
        assert record.signature is None
        assert record.content_hash is None
        assert record.verify_signature(_TEST_KEY_STR) is False, (
            "verify_signature() must return False for a record that was never signed"
        )

    @pytest.mark.parametrize("field,new_value", [
        ("event_id",        "tampered-event-id"),
        ("function_id",     "tampered-function"),
        ("duration",        999.999),
        ("memory_spike_kb", 99999),
        ("cpu_utilization", 99.9),
        ("network_io_bytes", 99999),
    ])
    def test_mutating_content_field_invalidates_signature(self, field: str, new_value: Any):
        """I-6 [8]: mutating any content field after signing invalidates verification."""
        record = _make_record()
        record.sign_record(_TEST_KEY_STR)
        # Sanity-check: verification passes before mutation
        assert record.verify_signature(_TEST_KEY_STR) is True, "Pre-condition failed"

        # Mutate the field directly — bypasses sign_record() intentionally
        object.__setattr__(record, field, new_value)

        # The stored signature and content_hash no longer match the mutated payload
        assert record.verify_signature(_TEST_KEY_STR) is False, (
            f"After mutating field '{field}' to {new_value!r}, "
            f"verify_signature() must return False"
        )

    def test_mutating_timestamp_invalidates_signature(self):
        """Timestamp mutation invalidates signature (timestamp is in content hash)."""
        record = _make_record()
        record.sign_record(_TEST_KEY_STR)
        original_ts = record.timestamp
        object.__setattr__(record, "timestamp", original_ts + 1000.0)
        assert record.verify_signature(_TEST_KEY_STR) is False, (
            "Mutating timestamp must invalidate the signature"
        )


class TestHmacSigningDeterminism:
    """
    Invariants 10–12: determinism, collision sensitivity, and idempotency.
    """

    def test_content_hash_is_deterministic(self):
        """I-6 [10]: signing the same record twice yields identical content_hash values."""
        record_a = _make_record()
        record_b = _make_record()  # separate instance, same data
        record_a.sign_record(_TEST_KEY_STR)
        record_b.sign_record(_TEST_KEY_STR)
        assert record_a.content_hash == record_b.content_hash, (
            f"content_hash must be deterministic.\n"
            f"  First:   {record_a.content_hash}\n"
            f"  Second:  {record_b.content_hash}"
        )

    def test_signature_is_deterministic(self):
        """Signing the same record twice yields identical signatures."""
        record_a = _make_record()
        record_b = _make_record()
        record_a.sign_record(_TEST_KEY_STR)
        record_b.sign_record(_TEST_KEY_STR)
        assert record_a.signature == record_b.signature, (
            f"signature must be deterministic.\n"
            f"  First:   {record_a.signature}\n"
            f"  Second:  {record_b.signature}"
        )

    @pytest.mark.parametrize("field,alt_value", [
        ("event_id",    "different-event-id"),
        ("function_id", "different-function"),
        ("duration",    1.5),
    ])
    def test_distinct_records_yield_distinct_content_hashes(
        self, field: str, alt_value: Any
    ):
        """I-6 [11]: records differing in any content field produce distinct content_hashes."""
        record_base = _make_record()
        record_alt  = _make_record(**{field: alt_value})
        record_base.sign_record(_TEST_KEY_STR)
        record_alt.sign_record(_TEST_KEY_STR)
        assert record_base.content_hash != record_alt.content_hash, (
            f"Records differing in '{field}' must have distinct content_hashes"
        )

    def test_signing_is_idempotent(self):
        """I-6 [12]: calling sign_record() twice does not raise and overwrites consistently."""
        record = _make_record()
        record.sign_record(_TEST_KEY_STR)
        hash_first = record.content_hash
        sig_first  = record.signature

        # Second call must not raise and must produce the same values
        record.sign_record(_TEST_KEY_STR)
        assert record.content_hash == hash_first, "Second sign_record() must yield same content_hash"
        assert record.signature    == sig_first,  "Second sign_record() must yield same signature"
        assert record.verify_signature(_TEST_KEY_STR) is True, (
            "Record must still be verifiable after second sign_record() call"
        )


class TestHmacSigningInvariantI6:
    """
    Omnibus tests directly asserting Invariant I-6 as stated in the blueprint.
    """

    def test_i6_full_round_trip(self):
        """
        I-6 [full]: create → sign → verify round-trip with independent re-computation.

        This is the canonical end-to-end proof of the invariant.  The test:
          1. Creates a TelemetryRecord with known content.
          2. Calls sign_record() with the test key.
          3. Asserts signature and content_hash are present and non-empty.
          4. Re-derives content_hash independently (SHA-256 of canonical JSON).
          5. Re-derives signature independently (HMAC-SHA256 of content_hash).
          6. Asserts both stored values match the independently computed values.
          7. Calls verify_signature() and asserts it returns True.
        """
        record = _make_record(
            event_id="i6-round-trip",
            duration=0.500,
            memory_spike_kb=512,
        )
        record.sign_record(_TEST_KEY_STR)

        # Step 3: presence
        assert record.signature is not None and len(record.signature) > 0
        assert record.content_hash is not None and len(record.content_hash) > 0
        assert record.signature_algorithm == "HMAC-SHA256"

        # Step 4–5: independent re-derivation
        expected_hash = _expected_content_hash(record)
        expected_sig  = _expected_hmac_signature(expected_hash, _TEST_KEY_STR)

        # Step 6: stored values match independently computed values
        assert record.content_hash == expected_hash, (
            f"content_hash mismatch: {record.content_hash!r} != {expected_hash!r}"
        )
        assert record.signature == expected_sig, (
            f"signature mismatch: {record.signature!r} != {expected_sig!r}"
        )

        # Step 7: native verification
        assert record.verify_signature(_TEST_KEY_STR) is True

    def test_i6_signed_records_survive_verify_across_multiple_anomaly_types(self):
        """I-6 applies to all AnomalyType values, not just BENIGN."""
        from layer0.app_telemetry import AnomalyType

        anomaly_types = [
            AnomalyType.BENIGN,
            AnomalyType.CPU_SPIKE,
            AnomalyType.MEMORY_SPIKE,
            AnomalyType.ADVERSARIAL_INJECTION,
            AnomalyType.DATA_EXFILTRATION,
            AnomalyType.SILENT_CORRUPTION,
        ]
        for atype in anomaly_types:
            record = _make_record(anomaly_type=atype)
            record.sign_record(_TEST_KEY_STR)
            assert record.verify_signature(_TEST_KEY_STR) is True, (
                f"verify_signature() failed for AnomalyType.{atype.name}"
            )
            # Also ensure hash was correctly set
            assert record.content_hash == _expected_content_hash(record), (
                f"content_hash mismatch for AnomalyType.{atype.name}"
            )

    def test_i6_signed_records_survive_verify_across_execution_phases(self):
        """I-6 applies across all ExecutionPhase values."""
        from layer0.app_telemetry import ExecutionPhase

        for phase in ExecutionPhase:
            record = _make_record(execution_phase=phase)
            record.sign_record(_TEST_KEY_STR)
            assert record.verify_signature(_TEST_KEY_STR) is True, (
                f"verify_signature() failed for ExecutionPhase.{phase.name}"
            )


# ---------------------------------------------------------------------------
# Allow running this file directly for quick smoke-testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
