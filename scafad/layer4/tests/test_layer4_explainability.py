"""
scafad/layer4/tests/test_layer4_explainability.py
==================================================

T-022 — Layer 4 tiered explainability unit tests.

Covers ExplainabilityDecisionEngine.build_trace() — the C-4 contribution:
budgeted tiered explainability (terse/standard/verbose with redaction budget).

WP: Day-4 (7-day sprint)
"""

from __future__ import annotations

import json
import unittest

from layer2.detection_matrix import DetectionSignal, Layer2DetectionResult
from layer3.trust_fusion import Layer3FusionResult
from layer4.explainability import (
    ExplainabilityDecisionEngine,
    Layer4DecisionTrace,
    VERBOSITY_LEVELS,
    _SENSITIVE_FIELDS_PRIORITY,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fusion(
    record_id: str = "rec-001",
    trace_id: str = "trace-001",
    fused_score: float = 0.5,
    risk_band: str = "medium",
    volatility_adjustment: float = 0.0,
    consensus_strength: float = 0.5,
    leading_signals: list | None = None,
) -> Layer3FusionResult:
    return Layer3FusionResult(
        record_id=record_id,
        trace_id=trace_id,
        fused_score=fused_score,
        volatility_adjustment=volatility_adjustment,
        trust_score_input=0.8,
        consensus_strength=consensus_strength,
        risk_band=risk_band,
        leading_signals=leading_signals or [],
    )


def _make_detection(
    record_id: str = "rec-001",
    signals: list | None = None,
    aggregate_score: float = 0.5,
    detector_consensus: float = 0.5,
    evidence_summary: list | None = None,
) -> Layer2DetectionResult:
    return Layer2DetectionResult(
        record_id=record_id,
        trace_id="trace-001",
        signals=signals or [],
        aggregate_score=aggregate_score,
        detector_consensus=detector_consensus,
        evidence_summary=evidence_summary or [],
    )


def _signal(name: str, score: float = 0.5, confidence: float = 0.8) -> DetectionSignal:
    return DetectionSignal(
        detector_name=name,
        score=score,
        confidence=confidence,
        rationale=f"{name} fired",
    )


def _build(
    fused_score: float = 0.5,
    verbosity: str = "standard",
    redaction_budget: int = 0,
    redacted_fields: list | None = None,
    signals: list | None = None,
    leading_signals: list | None = None,
    evidence_summary: list | None = None,
) -> Layer4DecisionTrace:
    engine = ExplainabilityDecisionEngine()
    _signals = signals or [_signal("det1")]
    _leading = leading_signals or [_signal("det1")]
    detection = _make_detection(signals=_signals, evidence_summary=evidence_summary or [])
    fusion = _make_fusion(fused_score=fused_score, leading_signals=_leading)
    return engine.build_trace(
        detection,
        fusion,
        verbosity=verbosity,
        redaction_budget=redaction_budget,
        redacted_fields=redacted_fields,
    )


# ---------------------------------------------------------------------------
# Tests: decision classification
# ---------------------------------------------------------------------------

class TestDecisionClassification(unittest.TestCase):
    """fused_score thresholds must map to the correct decision/severity/action."""

    def _trace(self, score: float) -> Layer4DecisionTrace:
        return _build(fused_score=score)

    def test_escalate_at_0_75(self) -> None:
        trace = self._trace(0.75)
        self.assertEqual(trace.decision, "escalate")
        self.assertEqual(trace.severity, "high")
        self.assertEqual(trace.recommended_action, "immediate_containment_review")

    def test_escalate_above_0_75(self) -> None:
        trace = self._trace(0.9)
        self.assertEqual(trace.decision, "escalate")

    def test_review_at_0_3(self) -> None:
        trace = self._trace(0.3)
        self.assertEqual(trace.decision, "review")
        self.assertEqual(trace.severity, "medium")
        self.assertEqual(trace.recommended_action, "analyst_triage")

    def test_review_between_0_3_and_0_75(self) -> None:
        trace = self._trace(0.5)
        self.assertEqual(trace.decision, "review")

    def test_observe_below_threshold(self) -> None:
        # WP-5.3: threshold recalibrated from 0.30 to 0.09 (maximises F1)
        # Score 0.05 is below the new threshold and must return "observe"
        trace = self._trace(0.05)
        self.assertEqual(trace.decision, "observe")
        self.assertEqual(trace.severity, "low")
        self.assertEqual(trace.recommended_action, "monitor")

    def test_review_at_calibrated_threshold(self) -> None:
        # WP-5.3: score at exactly the new threshold (0.09) must return "review"
        trace = self._trace(0.09)
        self.assertEqual(trace.decision, "review")
        self.assertEqual(trace.severity, "medium")
        self.assertEqual(trace.recommended_action, "analyst_triage")

    def test_observe_at_zero(self) -> None:
        trace = self._trace(0.0)
        self.assertEqual(trace.decision, "observe")


# ---------------------------------------------------------------------------
# Tests: verbosity tiers
# ---------------------------------------------------------------------------

class TestVerbosityTerse(unittest.TestCase):
    """Terse verbosity — only summary, no explanation_points, no evidence_items."""

    def setUp(self) -> None:
        sigs = [_signal("d1"), _signal("d2")]
        self.trace = _build(
            verbosity="terse",
            signals=sigs,
            leading_signals=sigs,
            evidence_summary=["ev1", "ev2"],
        )

    def test_verbosity_field_is_terse(self) -> None:
        self.assertEqual(self.trace.verbosity, "terse")

    def test_explanation_points_empty(self) -> None:
        self.assertEqual(self.trace.explanation_points, [])

    def test_evidence_items_empty(self) -> None:
        self.assertEqual(self.trace.evidence_items, [])

    def test_explanation_summary_present(self) -> None:
        self.assertTrue(len(self.trace.explanation_summary) > 0)

    def test_trace_metadata_empty_for_terse(self) -> None:
        self.assertEqual(self.trace.trace_metadata, {})


class TestVerbosityStandard(unittest.TestCase):
    """Standard verbosity — adds explanation_points for top-2 signals."""

    def setUp(self) -> None:
        leading = [_signal("top1", 0.9), _signal("top2", 0.7)]
        self.trace = _build(
            verbosity="standard",
            signals=leading + [_signal("d3", 0.2)],
            leading_signals=leading,
            evidence_summary=["ev1"],
        )

    def test_verbosity_field_is_standard(self) -> None:
        self.assertEqual(self.trace.verbosity, "standard")

    def test_explanation_points_not_empty(self) -> None:
        self.assertGreater(len(self.trace.explanation_points), 0)

    def test_explanation_points_at_most_two(self) -> None:
        self.assertLessEqual(len(self.trace.explanation_points), 2)

    def test_evidence_items_empty_for_standard(self) -> None:
        self.assertEqual(self.trace.evidence_items, [])

    def test_trace_metadata_present(self) -> None:
        self.assertIn("risk_band", self.trace.trace_metadata)
        self.assertIn("verbosity", self.trace.trace_metadata)

    def test_explanation_points_contain_signal_name(self) -> None:
        joined = " ".join(self.trace.explanation_points)
        self.assertIn("top1", joined)


class TestVerbosityVerbose(unittest.TestCase):
    """Verbose verbosity — adds all signals + evidence_items."""

    def setUp(self) -> None:
        sigs = [_signal(f"d{i}", score=float(i) / 10.0) for i in range(5)]
        self.trace = _build(
            verbosity="verbose",
            signals=sigs,
            leading_signals=sigs[:2],
            evidence_summary=["ev1", "ev2", "ev3"],
        )

    def test_verbosity_field_is_verbose(self) -> None:
        self.assertEqual(self.trace.verbosity, "verbose")

    def test_evidence_items_populated(self) -> None:
        self.assertEqual(self.trace.evidence_items, ["ev1", "ev2", "ev3"])

    def test_explanation_points_include_all_signals(self) -> None:
        # verbose includes all 5 signals, sorted descending
        self.assertEqual(len(self.trace.explanation_points), 5)

    def test_trace_metadata_includes_budget(self) -> None:
        self.assertIn("redaction_budget", self.trace.trace_metadata)


class TestVerbosityValidation(unittest.TestCase):
    """Invalid verbosity must raise ValueError."""

    def test_invalid_verbosity_raises(self) -> None:
        engine = ExplainabilityDecisionEngine()
        detection = _make_detection()
        fusion = _make_fusion()
        with self.assertRaises(ValueError):
            engine.build_trace(detection, fusion, verbosity="ultra")

    def test_all_three_valid_verbosity_levels_accepted(self) -> None:
        engine = ExplainabilityDecisionEngine()
        detection = _make_detection(signals=[_signal("d")])
        for level in ("terse", "standard", "verbose"):
            fusion = _make_fusion(leading_signals=[_signal("d")])
            trace = engine.build_trace(detection, fusion, verbosity=level)
            self.assertEqual(trace.verbosity, level)


# ---------------------------------------------------------------------------
# Tests: redaction budget
# ---------------------------------------------------------------------------

class TestRedactionBudget(unittest.TestCase):
    """Redaction budget must auto-redact up to N sensitive fields."""

    def test_budget_zero_no_auto_redaction(self) -> None:
        trace = _build(redaction_budget=0)
        # No auto-redaction; redacted_fields should be empty (no caller fields)
        self.assertEqual(trace.redacted_fields, [])

    def test_budget_one_redacts_highest_priority_field(self) -> None:
        trace = _build(redaction_budget=1)
        self.assertEqual(len(trace.redacted_fields), 1)
        self.assertEqual(trace.redacted_fields[0], _SENSITIVE_FIELDS_PRIORITY[0])

    def test_budget_three_redacts_three_fields(self) -> None:
        trace = _build(redaction_budget=3)
        self.assertEqual(len(trace.redacted_fields), 3)
        for i, expected in enumerate(_SENSITIVE_FIELDS_PRIORITY[:3]):
            self.assertEqual(trace.redacted_fields[i], expected)

    def test_budget_exceeds_pool_capped_at_pool_size(self) -> None:
        pool_size = len(_SENSITIVE_FIELDS_PRIORITY)
        trace = _build(redaction_budget=pool_size + 10)
        self.assertEqual(len(trace.redacted_fields), pool_size)

    def test_caller_fields_merged_with_auto_redacted(self) -> None:
        trace = _build(
            redaction_budget=1,
            redacted_fields=["my_custom_field"],
        )
        self.assertIn("my_custom_field", trace.redacted_fields)
        self.assertIn(_SENSITIVE_FIELDS_PRIORITY[0], trace.redacted_fields)

    def test_no_duplicates_in_merged_redacted_fields(self) -> None:
        # Pass the top-priority field as a caller field AND set budget=1
        top_field = _SENSITIVE_FIELDS_PRIORITY[0]
        trace = _build(
            redaction_budget=1,
            redacted_fields=[top_field],
        )
        self.assertEqual(trace.redacted_fields.count(top_field), 1)

    def test_negative_budget_raises(self) -> None:
        engine = ExplainabilityDecisionEngine()
        detection = _make_detection()
        fusion = _make_fusion()
        with self.assertRaises(ValueError):
            engine.build_trace(detection, fusion, redaction_budget=-1)


# ---------------------------------------------------------------------------
# Tests: field identity and I-15 contract
# ---------------------------------------------------------------------------

class TestFieldIdentityAndContract(unittest.TestCase):
    """record_id/trace_id preserved; to_dict() JSON-serialisable with required keys."""

    def test_record_id_preserved(self) -> None:
        detection = _make_detection(record_id="my-rec")
        fusion = _make_fusion(record_id="my-rec")
        engine = ExplainabilityDecisionEngine()
        trace = engine.build_trace(detection, fusion)
        self.assertEqual(trace.record_id, "my-rec")

    def test_trace_id_from_fusion(self) -> None:
        detection = _make_detection()
        fusion = _make_fusion(trace_id="fus-trace")
        engine = ExplainabilityDecisionEngine()
        trace = engine.build_trace(detection, fusion)
        self.assertEqual(trace.trace_id, "fus-trace")

    def test_to_dict_is_json_serialisable(self) -> None:
        trace = _build(verbosity="verbose", evidence_summary=["e1"])
        json.dumps(trace.to_dict())  # must not raise

    def test_to_dict_contains_required_keys(self) -> None:
        trace = _build()
        d = trace.to_dict()
        required = {
            "record_id", "trace_id", "decision", "severity", "verbosity",
            "explanation_summary", "explanation_points", "recommended_action",
            "evidence_items", "redacted_fields", "trace_metadata",
        }
        self.assertTrue(required.issubset(d.keys()),
                        f"Missing: {required - d.keys()}")

    def test_to_dict_all_verbosity_levels_serialisable(self) -> None:
        for level in ("terse", "standard", "verbose"):
            trace = _build(verbosity=level, evidence_summary=["e"])
            json.dumps(trace.to_dict())

    def test_custom_sensitive_pool_respected(self) -> None:
        engine = ExplainabilityDecisionEngine(
            sensitive_fields=["custom_a", "custom_b"]
        )
        detection = _make_detection()
        fusion = _make_fusion()
        trace = engine.build_trace(detection, fusion, redaction_budget=1)
        self.assertEqual(trace.redacted_fields, ["custom_a"])


if __name__ == "__main__":
    unittest.main()
