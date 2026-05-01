"""
scafad/tests/integration/test_e2e_pipeline.py
=============================================

Integration test suite: full end-to-end pipeline assertions for the SCAFAD
canonical runtime.

Drives synthetic telemetry events through :class:`SCAFADCanonicalRuntime` and
validates:

* **Full pipeline output shape** — layer0_record, layer1_record, and
  multilayer_result (L1..L5) are all populated on every successful run.
* **Invariant I-3** — record_id is identical at L1, L2, L3, L4, and L5.
* **Invariant I-4** — trace_id is identical at L1, L2, L3, L4, and L5.
* **Invariant I-6** — after calling ``sign_record()`` the layer0_record
  carries non-empty ``content_hash`` and ``signature`` fields that round-trip
  through ``verify_signature()``.
* **Invariant I-7** — ``quality_report.completeness_score`` ∈ [0.0, 1.0].

Coverage:
  - Benign event (normal operation, baseline)
  - DoS amplification anomaly
  - Data exfiltration anomaly
  - Crypto-mining anomaly
  - Cold-start anomaly
  - Malformed / sparse input (graceful degradation)
  - High-severity alert path (adversarial injection, elevated fused score)
  - Layer 6 analyst feedback activation
  - L0 detection enrichment verification
  - JSON serialisation of the full result
  - HMAC signing round-trip (I-6, 3 sub-tests)
"""

from __future__ import annotations

import json
import time
import unittest
import uuid
from typing import Any, Dict, Optional

from layer0.app_telemetry import (
    AnomalyType,
    ExecutionPhase,
    TelemetryRecord,
    TelemetrySource,
)
from runtime.runtime import CanonicalRuntimeResult, SCAFADCanonicalRuntime


# ---------------------------------------------------------------------------
# Shared runtime instance
# ---------------------------------------------------------------------------
# A single runtime is reused across all tests so the L0 engine's rolling
# window accumulates historical signal — this mirrors the intended production
# deployment pattern where the engine is a long-lived singleton.

_RUNTIME = SCAFADCanonicalRuntime()

# HMAC key used by I-6 signing tests.  The value is arbitrary; any non-empty
# string exercises the full sign/verify path.
_TEST_HMAC_KEY = "scafad-integration-test-secret-key-2026"


# ---------------------------------------------------------------------------
# Synthetic event factory
# ---------------------------------------------------------------------------

def _make_event(
    anomaly_type: str = "benign",
    execution_phase: str = "invoke",
    function_id: Optional[str] = None,
    duration: float = 200.0,
    cpu_utilization: float = 25.0,
    memory_spike_kb: int = 512,
    network_io_bytes: int = 4096,
    **extra: Any,
) -> Dict[str, Any]:
    """Return a minimal, valid synthetic event dict.

    All optional fields that the runtime can fill in with defaults are omitted
    so the integration tests verify the ``build_record()`` fallback behaviour
    rather than explicit data.  Additional keyword arguments are merged in to
    allow per-test customisation (e.g. ``adversarial_score=0.9``).

    Parameters
    ----------
    anomaly_type:
        Raw anomaly type string (e.g. ``"benign"``, ``"dos_amplification"``).
        Unmapped values silently fall back to ``"benign"`` inside
        :meth:`SCAFADCanonicalRuntime.build_record`.
    execution_phase:
        One of ``"init"``, ``"invoke"``, ``"shutdown"``, ``"error"``,
        ``"timeout"``.
    function_id:
        Lambda identifier; auto-generated from uuid if *None*.
    duration:
        Synthetic execution duration in milliseconds.
    cpu_utilization:
        CPU utilisation percentage (0–100).
    memory_spike_kb:
        Peak memory usage delta in kilobytes.
    network_io_bytes:
        Total network I/O in bytes.
    **extra:
        Forwarded verbatim into the event dict — use for scores, tags, etc.
    """
    event: Dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "function_id": function_id or f"lambda-{uuid.uuid4().hex[:8]}",
        "execution_phase": execution_phase,
        "anomaly_type": anomaly_type,
        "duration": duration,
        "cpu_utilization": cpu_utilization,
        "memory_spike_kb": memory_spike_kb,
        "network_io_bytes": network_io_bytes,
        "schema_version": "v4.2",
    }
    event.update(extra)
    return event


# ---------------------------------------------------------------------------
# Shared assertion helper
# ---------------------------------------------------------------------------

def _assert_pipeline_invariants(
    tc: unittest.TestCase,
    result: CanonicalRuntimeResult,
) -> None:
    """Assert full pipeline output shape plus Invariants I-3, I-4, and I-7.

    Called from every scenario test so invariant coverage is guaranteed without
    duplicating assertion logic across 13 test methods.

    Checks
    ------
    Shape:
        * ``layer0_record`` is not None
        * ``adapted_record`` is a dict
        * ``layer1_record`` is not None
        * ``multilayer_result`` is not None
        * ``multilayer_result.layer1`` through ``.layer5`` are not None

    I-3 — record_id stability:
        ``layer1_record.record_id`` equals the record_id on every multilayer
        layer (L2, L3, L4, L5).

    I-4 — trace_id stability:
        ``layer1_record.trace_id`` equals the trace_id on every multilayer
        layer (L2, L3, L4, L5).

    I-7 — completeness_score bounds:
        ``layer1_record.quality_report.completeness_score`` ∈ [0.0, 1.0].
    """
    # ---- Full output shape ------------------------------------------------
    tc.assertIsNotNone(result.layer0_record, "layer0_record must be present")
    tc.assertIsInstance(
        result.adapted_record, dict, "adapted_record must be a dict"
    )
    tc.assertIsNotNone(result.layer1_record, "layer1_record must be present")
    tc.assertIsNotNone(result.multilayer_result, "multilayer_result must be present")

    ml = result.multilayer_result
    tc.assertIsNotNone(ml.layer1, "multilayer_result.layer1 must be present")
    tc.assertIsNotNone(ml.layer2, "multilayer_result.layer2 must be present")
    tc.assertIsNotNone(ml.layer3, "multilayer_result.layer3 must be present")
    tc.assertIsNotNone(ml.layer4, "multilayer_result.layer4 must be present")
    tc.assertIsNotNone(ml.layer5, "multilayer_result.layer5 must be present")

    # ---- Invariant I-3: record_id stable from L1 through L5 --------------
    rec_id: str = result.layer1_record.record_id
    tc.assertIsInstance(rec_id, str, "record_id must be a string (I-3)")
    tc.assertGreater(len(rec_id), 0, "record_id must be non-empty (I-3)")
    tc.assertEqual(ml.layer2.record_id, rec_id,
                   "I-3 violated: record_id diverged at Layer 2")
    tc.assertEqual(ml.layer3.record_id, rec_id,
                   "I-3 violated: record_id diverged at Layer 3")
    tc.assertEqual(ml.layer4.record_id, rec_id,
                   "I-3 violated: record_id diverged at Layer 4")
    tc.assertEqual(ml.layer5.record_id, rec_id,
                   "I-3 violated: record_id diverged at Layer 5")

    # ---- Invariant I-4: trace_id stable from L1 through L5 ---------------
    trace_id: str = result.layer1_record.trace_id
    tc.assertIsInstance(trace_id, str, "trace_id must be a string (I-4)")
    tc.assertGreater(len(trace_id), 0, "trace_id must be non-empty (I-4)")
    tc.assertEqual(ml.layer2.trace_id, trace_id,
                   "I-4 violated: trace_id diverged at Layer 2")
    tc.assertEqual(ml.layer3.trace_id, trace_id,
                   "I-4 violated: trace_id diverged at Layer 3")
    tc.assertEqual(ml.layer4.trace_id, trace_id,
                   "I-4 violated: trace_id diverged at Layer 4")
    tc.assertEqual(ml.layer5.trace_id, trace_id,
                   "I-4 violated: trace_id diverged at Layer 5")

    # ---- Invariant I-7: completeness_score ∈ [0.0, 1.0] ------------------
    score: float = result.layer1_record.quality_report.completeness_score
    tc.assertGreaterEqual(score, 0.0,
                          f"I-7 violated: completeness_score={score} < 0.0")
    tc.assertLessEqual(score, 1.0,
                       f"I-7 violated: completeness_score={score} > 1.0")


# ===========================================================================
# Test class 1: End-to-end scenario tests
# ===========================================================================

class TestE2EPipelineScenarios(unittest.TestCase):
    """Full end-to-end scenario tests for SCAFADCanonicalRuntime.process_event().

    Each test method:
      1. Builds a synthetic event for a specific anomaly / scenario.
      2. Drives it through the canonical runtime via ``process_event()``.
      3. Calls ``_assert_pipeline_invariants()`` to validate the output shape
         and Invariants I-3, I-4, I-7.
      4. Adds scenario-specific assertions (L1 anomaly type, L3/L4 signals,
         L5 tactics, etc.).
    """

    # -----------------------------------------------------------------------
    # Scenario 1 — Benign event
    # -----------------------------------------------------------------------

    def test_benign_event_observe_decision(self) -> None:
        """Benign event must produce an 'observe' decision at Layer 4.

        This is the normal-operation baseline: a record with low resource
        usage and no anomaly signal must not be escalated.
        """
        event = _make_event(
            anomaly_type="benign",
            execution_phase="invoke",
            cpu_utilization=18.0,
            memory_spike_kb=300,    # WP-5.3: typical benign memory; ensures fused_score < 0.09
            network_io_bytes=4000,  # WP-5.3: typical benign network I/O
            duration=0.3,           # WP-5.3: 300 ms — matches eval-dataset benign profile (mean 0.27 s)
            function_id="baseline-lambda",
        )
        result = _RUNTIME.process_event(event)
        _assert_pipeline_invariants(self, result)

        # Benign anomaly type must survive as 'benign' at L1
        self.assertEqual(
            result.layer1_record.anomaly_type, "benign",
            "Benign event must have anomaly_type='benign' at Layer 1",
        )
        # A well-behaved benign event must produce the observe decision
        decision = result.multilayer_result.layer4.decision
        self.assertEqual(
            decision, "observe",
            f"Benign event must produce 'observe' decision at Layer 4, got {decision!r}",
        )
        # L3 risk band must be 'low' for a benign baseline
        self.assertEqual(
            result.multilayer_result.layer3.risk_band, "low",
            "Benign event must be classified 'low' risk at Layer 3",
        )

    # -----------------------------------------------------------------------
    # Scenario 2 — DoS amplification
    # -----------------------------------------------------------------------

    def test_dos_amplification_full_pipeline(self) -> None:
        """DoS amplification event drives all pipeline layers and preserves invariants.

        A high-volume network burst combined with sustained high CPU is the
        canonical DoS fingerprint: the detection matrix should fire and the
        L1 anomaly type must be promoted to 'malicious'.
        """
        event = _make_event(
            anomaly_type="dos_amplification",
            execution_phase="invoke",
            cpu_utilization=88.0,
            memory_spike_kb=65536,    # 64 MB surge
            network_io_bytes=2097152, # 2 MB burst — amplification fingerprint
            duration=3500.0,
            function_id="dos-target-lambda",
        )
        result = _RUNTIME.process_event(event)
        _assert_pipeline_invariants(self, result)

        # dos_amplification → 'malicious' after L0-L1 adapter mapping
        self.assertEqual(
            result.layer1_record.anomaly_type, "malicious",
            "dos_amplification must map to 'malicious' at Layer 1",
        )
        # At least one L2 detection signal must be generated for a DoS event
        self.assertGreater(
            len(result.multilayer_result.layer2.signals), 0,
            "DoS event must generate at least one Layer 2 detection signal",
        )
        # L3 fused_score must be a finite float
        fused = result.multilayer_result.layer3.fused_score
        self.assertIsInstance(fused, float, "fused_score must be a float")
        self.assertFalse(fused != fused, "fused_score must not be NaN")  # NaN check

    # -----------------------------------------------------------------------
    # Scenario 3 — Data exfiltration
    # -----------------------------------------------------------------------

    def test_data_exfiltration_full_pipeline(self) -> None:
        """Data exfiltration event drives all pipeline layers and preserves invariants.

        An unusually large outbound network volume is the primary exfiltration
        signal: the rule-chain engine flags the network_io_bytes threshold and
        semantic deviation flags the anomaly class.
        """
        event = _make_event(
            anomaly_type="data_exfiltration",
            execution_phase="invoke",
            cpu_utilization=72.0,
            memory_spike_kb=32768,
            network_io_bytes=104857600,  # 100 MB — suspicious exfil volume
            duration=1200.0,
            function_id="exfil-candidate-fn",
        )
        result = _RUNTIME.process_event(event)
        _assert_pipeline_invariants(self, result)

        # data_exfiltration → 'malicious'
        self.assertEqual(
            result.layer1_record.anomaly_type, "malicious",
            "data_exfiltration must map to 'malicious' at Layer 1",
        )
        # L5 tactics must be populated — exfiltration has well-known MITRE mappings
        self.assertGreater(
            len(result.multilayer_result.layer5.tactics), 0,
            "Data exfiltration event must produce at least one Layer 5 tactic",
        )
        # Adapted record must carry the expected schema_version key
        self.assertIn(
            "schema_version", result.adapted_record,
            "adapted_record must carry schema_version",
        )

    # -----------------------------------------------------------------------
    # Scenario 4 — Crypto-mining
    # -----------------------------------------------------------------------

    def test_cryptomining_full_pipeline(self) -> None:
        """Crypto-mining anomaly drives all pipeline layers and preserves invariants.

        Near-100 % sustained CPU is the hallmark of coin-miner workloads: the
        rule-chain engine fires on cpu_utilization >= 80 and the semantic
        deviation engine flags the 'malicious' anomaly class.
        """
        event = _make_event(
            anomaly_type="cryptomining",
            execution_phase="invoke",
            cpu_utilization=95.0,   # sustained near-100 % — mining fingerprint
            memory_spike_kb=8192,
            network_io_bytes=16384,
            duration=29800.0,       # long-running; 30-second Lambda timeout
            function_id="mining-suspect-fn",
        )
        result = _RUNTIME.process_event(event)
        _assert_pipeline_invariants(self, result)

        # cryptomining → 'malicious'
        self.assertEqual(
            result.layer1_record.anomaly_type, "malicious",
            "cryptomining must map to 'malicious' at Layer 1",
        )
        # L2 detection must indicate an anomaly for sustained-CPU workload
        self.assertGreater(
            len(result.multilayer_result.layer2.signals), 0,
            "Crypto-mining event must generate at least one Layer 2 detection signal",
        )
        # L3 risk_band must be a valid canonical value
        self.assertIn(
            result.multilayer_result.layer3.risk_band,
            {"low", "medium", "high"},
            "Layer 3 risk_band must be one of: low, medium, high",
        )

    # -----------------------------------------------------------------------
    # Scenario 5 — Cold start
    # -----------------------------------------------------------------------

    def test_cold_start_full_pipeline(self) -> None:
        """Cold-start anomaly drives all pipeline layers and preserves invariants.

        A cold-start is a normal operational event but with elevated init-phase
        latency; it maps to 'suspicious' at Layer 1 (not 'malicious').
        """
        event = _make_event(
            anomaly_type="cold_start",
            execution_phase="init",  # init phase is characteristic of cold starts
            cpu_utilization=45.0,
            memory_spike_kb=4096,
            network_io_bytes=512,
            duration=800.0,          # cold-start latency spike in ms
            function_id="cold-start-fn",
        )
        result = _RUNTIME.process_event(event)
        _assert_pipeline_invariants(self, result)

        # cold_start → 'suspicious' (not 'malicious')
        self.assertEqual(
            result.layer1_record.anomaly_type, "suspicious",
            "cold_start must map to 'suspicious' at Layer 1",
        )
        # Layer 4 decision is one of the three canonical values
        self.assertIn(
            result.multilayer_result.layer4.decision,
            {"observe", "review", "escalate"},
            "Layer 4 decision must be one of: observe, review, escalate",
        )
        # Execution phase must be mapped (init → initialization at L1)
        self.assertEqual(
            result.layer1_record.execution_phase, "initialization",
            "ExecutionPhase.INIT must map to 'initialization' at Layer 1",
        )

    # -----------------------------------------------------------------------
    # Scenario 6 — Malformed / sparse input
    # -----------------------------------------------------------------------

    def test_malformed_event_graceful_handling(self) -> None:
        """A sparse / malformed event must not crash the pipeline.

        The canonical runtime is designed to degrade gracefully:
        * A missing ``event_id`` is synthesised internally.
        * An unknown ``anomaly_type`` string falls back to BENIGN.
        * All pipeline invariants still hold on the synthetic fallback record.
        """
        # Intentionally omit event_id, use an unknown anomaly type, and set
        # all numeric fields to zero to exercise the fallback paths.
        malformed_event: Dict[str, Any] = {
            # No event_id  → runtime synthesises "runtime-event" → uuid generated
            "function_id": "sparse-lambda",
            "anomaly_type": "COMPLETELY_UNKNOWN_TYPE_XYZ",  # unmapped → BENIGN
            "execution_phase": "invoke",
            "timestamp": time.time(),           # valid timestamp to pass L1 validation
            "duration": 0.0,
            "cpu_utilization": 0.0,
            "memory_spike_kb": 0,
            "network_io_bytes": 0,
        }
        result = _RUNTIME.process_event(malformed_event)
        _assert_pipeline_invariants(self, result)

        # Unknown anomaly type falls back to BENIGN → 'benign' at Layer 1
        self.assertEqual(
            result.layer1_record.anomaly_type, "benign",
            "Unknown anomaly_type string must fall back to 'benign' at Layer 1",
        )
        # Pipeline must complete without raising; result must be JSON-serialisable
        payload = result.to_dict()
        self.assertIn("layer0_record", payload)
        self.assertIn("layer1_record", payload)

    # -----------------------------------------------------------------------
    # Scenario 7 — High-severity alert path
    # -----------------------------------------------------------------------

    def test_high_severity_alert_path(self) -> None:
        """Extreme adversarial event must produce an elevated Layer 4 decision.

        The rule-chain engine fires on all four thresholds (cpu >= 80,
        memory >= 128 MB, network >= 4 KB, duration >= 1 ms).  The semantic
        deviation engine scores 'malicious' highly.  Together they push
        fused_score above 0.3, yielding a 'review' or 'escalate' decision.
        """
        event = _make_event(
            anomaly_type="adversarial_injection",
            execution_phase="invoke",
            cpu_utilization=98.5,
            memory_spike_kb=524288,    # 512 MB memory spike
            network_io_bytes=8388608,  # 8 MB unusual outbound traffic
            duration=4500.0,           # 4.5 s execution — far above threshold
            function_id="adversarial-target-fn",
        )
        result = _RUNTIME.process_event(event)
        _assert_pipeline_invariants(self, result)

        # adversarial_injection → 'malicious' at Layer 1
        self.assertEqual(
            result.layer1_record.anomaly_type, "malicious",
            "adversarial_injection must map to 'malicious' at Layer 1",
        )
        # L3 fused_score must be elevated (all four rule-chain thresholds fire)
        fused_score = result.multilayer_result.layer3.fused_score
        self.assertGreater(
            fused_score, 0.0,
            "Extreme adversarial event must produce fused_score > 0.0 at Layer 3",
        )
        # L4 decision must be elevated — this event saturates all detection signals
        decision = result.multilayer_result.layer4.decision
        self.assertIn(
            decision, {"review", "escalate"},
            f"High-severity adversarial event must not produce 'observe'; "
            f"got {decision!r} (fused_score={fused_score:.4f})",
        )

    # -----------------------------------------------------------------------
    # Scenario 8 — Full JSON serialisation
    # -----------------------------------------------------------------------

    def test_full_result_json_serializable(self) -> None:
        """CanonicalRuntimeResult.to_dict() must produce a JSON-serialisable payload.

        This test verifies the integration-layer contract: the runtime result
        can be written to a log store or a Lambda response body without errors.
        """
        event = _make_event(anomaly_type="benign")
        result = _RUNTIME.process_event(event)
        _assert_pipeline_invariants(self, result)

        payload = result.to_dict()

        # Top-level keys must be present
        for key in ("layer0_record", "adapted_record", "layer1_record", "multilayer_result"):
            self.assertIn(key, payload, f"to_dict() must include '{key}'")

        # Nested multilayer keys
        ml_payload = payload["multilayer_result"]
        for key in ("layer1", "layer2", "layer3", "layer4", "layer5"):
            self.assertIn(key, ml_payload,
                          f"multilayer_result dict must include '{key}'")

        # Full round-trip through json.dumps must succeed without error
        serialised = json.dumps(payload)
        self.assertIsInstance(serialised, str)
        self.assertGreater(len(serialised), 200,
                           "Serialised result must be non-trivial (> 200 chars)")

    # -----------------------------------------------------------------------
    # Scenario 9 — Layer 6 analyst feedback activation
    # -----------------------------------------------------------------------

    def test_layer6_activated_by_analyst_label(self) -> None:
        """Providing analyst_label to process_event must activate the L6 feedback path.

        Without an analyst_label, layer6 is None (by design).  Supplying one
        must activate the FeedbackLearningEngine and populate layer6.
        """
        event = _make_event(
            anomaly_type="dos_amplification",
            cpu_utilization=80.0,
            memory_spike_kb=65536,
            network_io_bytes=1048576,
        )
        result = _RUNTIME.process_event(event, analyst_label="confirmed")
        _assert_pipeline_invariants(self, result)

        self.assertIsNotNone(
            result.multilayer_result.layer6,
            "layer6 must be populated when analyst_label is provided",
        )
        # The layer6 feedback result must carry a valid adjusted_trust in [0, 1]
        adjusted_trust = result.multilayer_result.layer6.adjusted_trust
        self.assertGreaterEqual(adjusted_trust, 0.0,
                                "adjusted_trust must be >= 0.0")
        self.assertLessEqual(adjusted_trust, 1.0,
                             "adjusted_trust must be <= 1.0")
        # layer6 must be JSON-serialisable
        json.dumps(result.multilayer_result.layer6.to_dict())

    # -----------------------------------------------------------------------
    # Scenario 10 — L0 26-detector enrichment verification
    # -----------------------------------------------------------------------

    def test_l0_enrichment_sets_detection_summary(self) -> None:
        """The L0 26-detector panel must write l0_detection_summary into custom_fields.

        This test proves the full C-2 enrichment path is active in the
        canonical runtime, not just in the unit tests for the detection engine.
        """
        event = _make_event(anomaly_type="benign")
        result = _RUNTIME.process_event(event)
        _assert_pipeline_invariants(self, result)

        # Summary dict must be written by _enrich_record() before L1 processing
        summary = result.layer0_record.custom_fields.get("l0_detection_summary")
        self.assertIsNotNone(
            summary,
            "l0_detection_summary must be present in layer0_record.custom_fields",
        )

        # Required keys from the _enrich_record implementation
        for key in ("trust_weighted_score", "combined_confidence",
                    "final_anomaly_detected", "detector_count"):
            self.assertIn(
                key, summary,
                f"l0_detection_summary must include key '{key}'",
            )

        # All 26 detectors must have run
        self.assertEqual(
            summary["detector_count"], 26,
            "l0_detection_summary must report exactly 26 detectors",
        )

        # The summary must flow through the adapter into context_metadata
        custom = result.adapted_record.get("context_metadata", {}).get("custom_fields", {})
        self.assertIn(
            "l0_detection_summary", custom,
            "l0_detection_summary must be present in adapted_record.context_metadata.custom_fields",
        )


# ===========================================================================
# Test class 2: Invariant I-6 — HMAC signing round-trip
# ===========================================================================

class TestInvariantI6HMACSigning(unittest.TestCase):
    """I-6: layer0_record carries content_hash and signature after sign_record().

    The HMAC signing API was implemented in WP-4.9.  These three tests verify
    the full round-trip through a pipeline-processed record:

      1. ``content_hash`` is None before signing and non-empty after.
      2. ``signature`` is None before signing and non-empty after.
      3. ``verify_signature()`` returns True with the correct key and False
         with a wrong key.
    """

    def _process_event(self, anomaly_type: str = "benign") -> CanonicalRuntimeResult:
        """Helper: run a synthetic event through the runtime and return the result."""
        event = _make_event(anomaly_type=anomaly_type)
        return _RUNTIME.process_event(event)

    # -----------------------------------------------------------------------
    # I-6 a — content_hash
    # -----------------------------------------------------------------------

    def test_i6_content_hash_set_after_sign_record(self) -> None:
        """content_hash must be a non-empty string after calling sign_record().

        Verifies I-6 precondition (None before signing) and postcondition
        (non-empty hex string after signing).
        """
        result = self._process_event()
        _assert_pipeline_invariants(self, result)

        record = result.layer0_record

        # Pre-condition: hash is None before signing
        self.assertIsNone(
            record.content_hash,
            "I-6 precondition: content_hash must be None before sign_record() is called",
        )

        record.sign_record(_TEST_HMAC_KEY)

        # Post-condition: hash is a non-empty hex string
        self.assertIsNotNone(
            record.content_hash,
            "I-6: content_hash must be set after sign_record()",
        )
        self.assertIsInstance(record.content_hash, str,
                              "I-6: content_hash must be a string")
        self.assertGreater(len(record.content_hash), 0,
                           "I-6: content_hash must be non-empty")

    # -----------------------------------------------------------------------
    # I-6 b — signature
    # -----------------------------------------------------------------------

    def test_i6_signature_set_after_sign_record(self) -> None:
        """signature must be a non-empty string after calling sign_record().

        Verifies the HMAC-SHA256 signing step populates the ``signature``
        attribute on the layer0_record returned from the pipeline.
        """
        result = self._process_event()
        _assert_pipeline_invariants(self, result)

        record = result.layer0_record

        # Pre-condition: signature is None before signing
        self.assertIsNone(
            record.signature,
            "I-6 precondition: signature must be None before sign_record() is called",
        )

        record.sign_record(_TEST_HMAC_KEY)

        # Post-condition: signature is a non-empty hex string
        self.assertIsNotNone(
            record.signature,
            "I-6: signature must be set after sign_record()",
        )
        self.assertIsInstance(record.signature, str,
                              "I-6: signature must be a string")
        self.assertGreater(len(record.signature), 0,
                           "I-6: signature must be non-empty")

    # -----------------------------------------------------------------------
    # I-6 c — verify_signature round-trip
    # -----------------------------------------------------------------------

    def test_i6_verify_signature_round_trip(self) -> None:
        """verify_signature() must return True with the correct key and False
        with a wrong key after sign_record().

        This is the full I-6 round-trip: process → sign → verify (correct) →
        verify (wrong key).  Using a data_exfiltration event to exercise signing
        on a non-benign, fully-populated pipeline output.
        """
        result = self._process_event(anomaly_type="data_exfiltration")
        _assert_pipeline_invariants(self, result)

        record = result.layer0_record
        record.sign_record(_TEST_HMAC_KEY)

        # Correct key → valid signature
        self.assertTrue(
            record.verify_signature(_TEST_HMAC_KEY),
            "I-6: verify_signature must return True when the correct key is used",
        )
        # Wrong key → invalid signature (tamper detection)
        self.assertFalse(
            record.verify_signature("wrong-key-that-should-not-match"),
            "I-6: verify_signature must return False when the wrong key is used",
        )


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main()
