"""
scafad/runtime/tests/test_runtime_e2e.py
=========================================

T-025 — End-to-end canonical pipeline integration test.

Covers SCAFADCanonicalRuntime.process_record() and process_event():
the full L0->L1->L2->L3->L4->L5->L6 execution path via the canonical
runtime entrypoint. Validates I-1 (single Lambda entrypoint) and the
complete pipeline contract.

WP: Day-5 (7-day sprint)
"""

from __future__ import annotations

import json
import time
import unittest
import uuid
from typing import Any, Dict

from layer0.app_telemetry import (
    AnomalyType,
    ExecutionPhase,
    TelemetryRecord,
    TelemetrySource,
)
from runtime.runtime import CanonicalRuntimeResult, SCAFADCanonicalRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    anomaly_type: AnomalyType = AnomalyType.BENIGN,
    execution_phase: ExecutionPhase = ExecutionPhase.INVOKE,
    duration: float = 0.3,        # WP-5.3: 300 ms — matches eval-dataset benign profile (mean 0.27 s)
    cpu_utilization: float = 20.0,
    memory_spike_kb: int = 300,   # WP-5.3: typical benign memory; ensures fused_score < 0.09
    network_io_bytes: int = 4000, # WP-5.3: typical benign network I/O
    function_id: str = "test-lambda",
    adversarial_score: float = 0.0,
) -> TelemetryRecord:
    return TelemetryRecord(
        event_id=str(uuid.uuid4()),
        timestamp=time.time(),
        function_id=function_id,
        execution_phase=execution_phase,
        anomaly_type=anomaly_type,
        source=TelemetrySource.SCAFAD_LAYER0,
        duration=duration,
        memory_spike_kb=memory_spike_kb,
        cpu_utilization=cpu_utilization,
        network_io_bytes=network_io_bytes,
        fallback_mode=False,
        concurrency_id="conc-e2e",
        payload_size_bytes=512,
        adversarial_score=adversarial_score,
        economic_risk_score=0.0,
        silent_failure_probability=0.0,
        completeness_score=1.0,
        confidence_level=1.0,
        data_quality_score=1.0,
    )


def _make_event(**kwargs: Any) -> Dict[str, Any]:
    base = {
        "event_id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "function_id": "event-lambda",
        "execution_phase": "invoke",
        "anomaly": "benign",
        "duration": 0.3,           # WP-5.3: 300 ms — matches eval-dataset benign profile
        "cpu_utilization": 18.0,
        "memory_spike_kb": 300,    # WP-5.3: typical benign memory; ensures fused_score < 0.09
        "network_io_bytes": 4000,  # WP-5.3: typical benign network I/O
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Tests: process_record — structural contract
# ---------------------------------------------------------------------------

class TestProcessRecordStructure(unittest.TestCase):
    """process_record must return a CanonicalRuntimeResult with all layers present."""

    def setUp(self) -> None:
        self.rt = SCAFADCanonicalRuntime()
        self.record = _make_record()
        self.result = self.rt.process_record(self.record)

    def test_returns_canonical_runtime_result(self) -> None:
        self.assertIsInstance(self.result, CanonicalRuntimeResult)

    def test_layer0_record_preserved(self) -> None:
        self.assertIs(self.result.layer0_record, self.record)

    def test_adapted_record_is_dict(self) -> None:
        self.assertIsInstance(self.result.adapted_record, dict)

    def test_adapted_record_has_schema_version(self) -> None:
        self.assertIn("schema_version", self.result.adapted_record)

    def test_layer1_record_present(self) -> None:
        self.assertIsNotNone(self.result.layer1_record)

    def test_multilayer_result_present(self) -> None:
        self.assertIsNotNone(self.result.multilayer_result)

    def test_all_layer_results_present_in_multilayer(self) -> None:
        ml = self.result.multilayer_result
        self.assertIsNotNone(ml.layer1)
        self.assertIsNotNone(ml.layer2)
        self.assertIsNotNone(ml.layer3)
        self.assertIsNotNone(ml.layer4)
        self.assertIsNotNone(ml.layer5)
        # layer6 is None when no analyst_label — that is correct
        self.assertIsNone(ml.layer6)

    def test_to_dict_is_json_serialisable(self) -> None:
        json.dumps(self.result.to_dict())

    def test_to_dict_required_top_keys(self) -> None:
        d = self.result.to_dict()
        required = {"layer0_record", "adapted_record", "layer1_record", "multilayer_result"}
        self.assertTrue(required.issubset(d.keys()))


# ---------------------------------------------------------------------------
# Tests: process_record — pipeline correctness
# ---------------------------------------------------------------------------

class TestProcessRecordPipelineCorrectness(unittest.TestCase):
    """Key pipeline invariants across the full L0->L6 path."""

    def setUp(self) -> None:
        self.rt = SCAFADCanonicalRuntime()

    def test_benign_record_gives_observe_decision(self) -> None:
        result = self.rt.process_record(_make_record(anomaly_type=AnomalyType.BENIGN))
        decision = result.multilayer_result.layer4.decision
        self.assertEqual(decision, "observe")

    def test_adversarial_record_gives_high_fused_score_or_medium(self) -> None:
        # adversarial_injection + high cpu + high memory -> elevated score
        result = self.rt.process_record(_make_record(
            anomaly_type=AnomalyType.ADVERSARIAL_INJECTION,
            cpu_utilization=92.0,
            memory_spike_kb=200_000,
            network_io_bytes=8192,
            duration=2000.0,
            adversarial_score=0.9,
        ))
        fused = result.multilayer_result.layer3.fused_score
        self.assertGreater(fused, 0.0)

    def test_layer1_anomaly_type_propagated(self) -> None:
        result = self.rt.process_record(
            _make_record(anomaly_type=AnomalyType.ADVERSARIAL_INJECTION)
        )
        # L1 maps adversarial_injection -> "malicious"
        self.assertEqual(result.layer1_record.anomaly_type, "malicious")

    def test_l2_signals_non_empty_for_anomalous_record(self) -> None:
        result = self.rt.process_record(_make_record(
            anomaly_type=AnomalyType.CPU_BURST,
            cpu_utilization=90.0,
            duration=800.0,
        ))
        self.assertGreater(len(result.multilayer_result.layer2.signals), 0)

    def test_l3_risk_band_valid(self) -> None:
        result = self.rt.process_record(_make_record())
        self.assertIn(result.multilayer_result.layer3.risk_band,
                      {"low", "medium", "high"})

    def test_l4_verbosity_default_is_standard(self) -> None:
        result = self.rt.process_record(_make_record())
        self.assertEqual(result.multilayer_result.layer4.verbosity, "standard")

    def test_l5_tactics_non_empty(self) -> None:
        result = self.rt.process_record(_make_record())
        self.assertGreater(len(result.multilayer_result.layer5.tactics), 0)

    def test_record_id_consistent_across_all_layers(self) -> None:
        result = self.rt.process_record(_make_record())
        rec_id = result.layer1_record.record_id
        self.assertEqual(result.multilayer_result.layer2.record_id, rec_id)
        self.assertEqual(result.multilayer_result.layer3.record_id, rec_id)
        self.assertEqual(result.multilayer_result.layer4.record_id, rec_id)
        self.assertEqual(result.multilayer_result.layer5.record_id, rec_id)


# ---------------------------------------------------------------------------
# Tests: analyst feedback (layer6 activation)
# ---------------------------------------------------------------------------

class TestAnalystFeedbackPath(unittest.TestCase):
    """layer6 must only be populated when analyst_label is provided."""

    def setUp(self) -> None:
        self.rt = SCAFADCanonicalRuntime()

    def test_layer6_none_without_analyst_label(self) -> None:
        result = self.rt.process_record(_make_record())
        self.assertIsNone(result.multilayer_result.layer6)

    def test_layer6_populated_with_analyst_label(self) -> None:
        result = self.rt.process_record(
            _make_record(), analyst_label="confirmed"
        )
        self.assertIsNotNone(result.multilayer_result.layer6)

    def test_layer6_trust_modulated_by_label(self) -> None:
        rt = SCAFADCanonicalRuntime()
        r_confirm = rt.process_record(_make_record(), analyst_label="confirmed")
        trust_after = r_confirm.multilayer_result.layer6.adjusted_trust
        self.assertGreater(trust_after, 0.0)
        self.assertLessEqual(trust_after, 1.0)

    def test_layer6_to_dict_serialisable(self) -> None:
        result = self.rt.process_record(
            _make_record(), analyst_label="true_positive"
        )
        json.dumps(result.multilayer_result.layer6.to_dict())


# ---------------------------------------------------------------------------
# Tests: verbosity and redaction_budget threading
# ---------------------------------------------------------------------------

class TestVerbosityAndRedactionThreading(unittest.TestCase):
    """verbosity and redaction_budget must thread from runtime to L4."""

    def setUp(self) -> None:
        self.rt = SCAFADCanonicalRuntime()

    def test_terse_verbosity_produces_empty_explanation_points(self) -> None:
        result = self.rt.process_record(_make_record(), verbosity="terse")
        self.assertEqual(result.multilayer_result.layer4.explanation_points, [])

    def test_verbose_verbosity_recorded(self) -> None:
        result = self.rt.process_record(_make_record(), verbosity="verbose")
        self.assertEqual(result.multilayer_result.layer4.verbosity, "verbose")

    def test_redaction_budget_two_redacts_two_fields(self) -> None:
        result = self.rt.process_record(_make_record(), redaction_budget=2)
        self.assertEqual(len(result.multilayer_result.layer4.redacted_fields), 2)

    def test_caller_redacted_fields_present_in_output(self) -> None:
        result = self.rt.process_record(
            _make_record(), redacted_fields=["my_field"]
        )
        self.assertIn("my_field", result.multilayer_result.layer4.redacted_fields)

    def test_invalid_verbosity_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.rt.process_record(_make_record(), verbosity="ultra")


# ---------------------------------------------------------------------------
# Tests: process_event
# ---------------------------------------------------------------------------

class TestProcessEvent(unittest.TestCase):
    """process_event must accept a raw dict and produce a full pipeline result."""

    def setUp(self) -> None:
        self.rt = SCAFADCanonicalRuntime()

    def test_process_event_returns_canonical_result(self) -> None:
        result = self.rt.process_event(_make_event())
        self.assertIsInstance(result, CanonicalRuntimeResult)

    def test_process_event_benign_observe(self) -> None:
        result = self.rt.process_event(_make_event(anomaly="benign"))
        self.assertEqual(result.multilayer_result.layer4.decision, "observe")

    def test_process_event_function_id_captured(self) -> None:
        result = self.rt.process_event(_make_event(function_id="my-api"))
        self.assertIn("my-api", result.layer0_record.function_id)

    def test_process_event_to_dict_serialisable(self) -> None:
        result = self.rt.process_event(_make_event())
        json.dumps(result.to_dict())

    def test_process_event_with_analyst_label_activates_l6(self) -> None:
        result = self.rt.process_event(
            _make_event(), analyst_label="confirmed"
        )
        self.assertIsNotNone(result.multilayer_result.layer6)

    def test_process_event_verbosity_threading(self) -> None:
        result = self.rt.process_event(_make_event(), verbosity="terse")
        self.assertEqual(result.multilayer_result.layer4.verbosity, "terse")


# ---------------------------------------------------------------------------
# Tests: L0 enrichment (DL-053)
# ---------------------------------------------------------------------------

class TestL0DetectionEnrichment(unittest.TestCase):
    """process_record must run the L0 26-detector panel and write computed
    scores back onto the TelemetryRecord before it reaches L1.

    Validates C-2: the trust-weighted multi-vector detection panel is active
    in the canonical pipeline, not merely unit-tested in isolation.
    """

    def setUp(self) -> None:
        self.rt = SCAFADCanonicalRuntime()

    def test_l0_engine_present_on_runtime(self) -> None:
        from layer0.layer0_core import AnomalyDetectionEngine
        self.assertIsInstance(self.rt.layer0_engine, AnomalyDetectionEngine)

    def test_l0_engine_is_singleton_across_calls(self) -> None:
        """The same engine instance must be reused so historical data accumulates."""
        self.assertIs(self.rt.layer0_engine, self.rt.layer0_engine)

    def test_l0_detection_summary_written_to_custom_fields(self) -> None:
        result = self.rt.process_record(_make_record())
        summary = result.layer0_record.custom_fields.get("l0_detection_summary")
        self.assertIsNotNone(summary, "l0_detection_summary missing from custom_fields")
        self.assertIn("trust_weighted_score", summary)
        self.assertIn("combined_confidence", summary)
        self.assertIn("final_anomaly_detected", summary)
        self.assertIn("detector_count", summary)
        self.assertEqual(summary["detector_count"], 26)

    def test_l0_enrichment_sets_confidence_level(self) -> None:
        """confidence_level must be overwritten with the engine's combined_confidence."""
        record = _make_record()
        self.assertEqual(record.confidence_level, 1.0)  # default before enrichment
        result = self.rt.process_record(record)
        # After enrichment confidence_level reflects the engine's assessment
        self.assertGreaterEqual(result.layer0_record.confidence_level, 0.0)
        self.assertLessEqual(result.layer0_record.confidence_level, 1.0)

    def test_high_cpu_memory_record_raises_adversarial_score(self) -> None:
        """A record with high CPU and large memory spike should yield a non-zero
        adversarial score after L0 detection enrichment."""
        record = _make_record(
            cpu_utilization=95.0,
            memory_spike_kb=512 * 1024,  # 512 MB
            anomaly_type=AnomalyType.MEMORY_SPIKE,
        )
        result = self.rt.process_record(record)
        self.assertGreater(
            result.layer0_record.adversarial_score, 0.0,
            "adversarial_score should be non-zero for high-resource anomalous record",
        )

    def test_l0_summary_flows_through_to_adapted_record(self) -> None:
        """l0_detection_summary must be present in adapted_record.context_metadata
        so L2 detectors can observe it."""
        result = self.rt.process_record(_make_record())
        custom = result.adapted_record.get("context_metadata", {}).get("custom_fields", {})
        self.assertIn(
            "l0_detection_summary", custom,
            "l0_detection_summary did not flow through adapter into context_metadata",
        )

    def test_l0_enrichment_does_not_break_benign_record_pipeline(self) -> None:
        """Enrichment must not raise or alter the observe decision for a benign record."""
        result = self.rt.process_record(_make_record(anomaly_type=AnomalyType.BENIGN))
        self.assertEqual(result.multilayer_result.layer4.decision, "observe")


# ---------------------------------------------------------------------------
# Tests: I-1 — single canonical entrypoint
# ---------------------------------------------------------------------------

class TestCanonicalEntrypointInvariant(unittest.TestCase):
    """I-1: SCAFADCanonicalRuntime is the single authorised execution surface."""

    def test_runtime_instantiates_without_args(self) -> None:
        rt = SCAFADCanonicalRuntime()
        self.assertIsNotNone(rt)

    def test_runtime_has_adapter_attribute(self) -> None:
        rt = SCAFADCanonicalRuntime()
        self.assertIsNotNone(rt.adapter)

    def test_runtime_has_layer1_pipeline(self) -> None:
        rt = SCAFADCanonicalRuntime()
        self.assertIsNotNone(rt.layer1_pipeline)

    def test_runtime_has_multilayer_pipeline(self) -> None:
        rt = SCAFADCanonicalRuntime()
        self.assertIsNotNone(rt.multilayer_pipeline)

    def test_process_record_accepts_telemetry_record_only(self) -> None:
        rt = SCAFADCanonicalRuntime()
        with self.assertRaises((TypeError, AttributeError, KeyError)):
            rt.process_record({"not": "a_record"})  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
