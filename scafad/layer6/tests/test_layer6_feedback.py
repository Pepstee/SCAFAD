"""
scafad/layer6/tests/test_layer6_feedback.py
============================================

T-024 — Layer 6 feedback-learning unit tests.

Covers FeedbackLearningEngine.ingest_feedback() — analyst labels drive
trust modulation; trust is clamped to [0.1, 1.0]; replay queue grows;
priority escalates with tactics or high trust.

WP: Day-4 (7-day sprint)
"""

from __future__ import annotations

import json
import unittest

from layer5.threat_alignment import ThreatAlignmentResult
from layer6.feedback_learning import (
    FeedbackEvent,
    FeedbackLearningEngine,
    Layer6FeedbackState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_threat(
    record_id: str = "rec-001",
    trace_id: str = "trace-001",
    tactics: list | None = None,
    techniques: list | None = None,
    alignment_confidence: float = 0.5,
    campaign_cluster: str = "review-collection",
    attack_story: str = "Test story.",
) -> ThreatAlignmentResult:
    return ThreatAlignmentResult(
        record_id=record_id,
        trace_id=trace_id,
        tactics=tactics or ["collection"],
        techniques=techniques or ["telemetry-observation"],
        campaign_cluster=campaign_cluster,
        alignment_confidence=alignment_confidence,
        attack_story=attack_story,
    )


def _ingest(
    engine: FeedbackLearningEngine,
    analyst_label: str = "confirmed",
    record_id: str = "rec-001",
    trace_id: str = "trace-001",
    tactics: list | None = None,
    alignment_confidence: float = 0.5,
) -> Layer6FeedbackState:
    threat = _make_threat(
        record_id=record_id,
        trace_id=trace_id,
        tactics=tactics,
        alignment_confidence=alignment_confidence,
    )
    return engine.ingest_feedback(record_id, trace_id, analyst_label, threat)


# ---------------------------------------------------------------------------
# Tests: trust modulation
# ---------------------------------------------------------------------------

class TestTrustModulation(unittest.TestCase):
    """Analyst labels must drive trust up or down by the expected delta."""

    def test_confirmed_label_increases_trust(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.8)
        state = _ingest(engine, analyst_label="confirmed")
        self.assertGreater(state.adjusted_trust, 0.8)

    def test_malicious_label_increases_trust(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.8)
        state = _ingest(engine, analyst_label="malicious")
        self.assertGreater(state.adjusted_trust, 0.8)

    def test_true_positive_label_increases_trust(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.8)
        state = _ingest(engine, analyst_label="true_positive")
        self.assertGreater(state.adjusted_trust, 0.8)

    def test_false_positive_label_decreases_trust(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.8)
        state = _ingest(engine, analyst_label="false_positive")
        self.assertLess(state.adjusted_trust, 0.8)

    def test_unknown_label_decreases_trust(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.8)
        state = _ingest(engine, analyst_label="unrecognised_label")
        self.assertLess(state.adjusted_trust, 0.8)

    def test_impact_tactic_adds_extra_delta(self) -> None:
        engine_impact = FeedbackLearningEngine(initial_trust=0.5)
        engine_plain = FeedbackLearningEngine(initial_trust=0.5)
        state_impact = _ingest(engine_impact, "confirmed", tactics=["impact"])
        state_plain = _ingest(engine_plain, "confirmed", tactics=["collection"])
        self.assertGreater(state_impact.adjusted_trust, state_plain.adjusted_trust)

    def test_high_alignment_confidence_adds_extra_delta(self) -> None:
        engine_high = FeedbackLearningEngine(initial_trust=0.5)
        engine_low = FeedbackLearningEngine(initial_trust=0.5)
        state_high = _ingest(engine_high, "confirmed", alignment_confidence=0.8)
        state_low = _ingest(engine_low, "confirmed", alignment_confidence=0.3)
        self.assertGreater(state_high.adjusted_trust, state_low.adjusted_trust)


# ---------------------------------------------------------------------------
# Tests: trust clamping
# ---------------------------------------------------------------------------

class TestTrustClamping(unittest.TestCase):
    """adjusted_trust must remain in [0.1, 1.0]."""

    def test_trust_never_exceeds_1_0(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.99)
        for _ in range(10):
            state = _ingest(engine, "confirmed", tactics=["impact"],
                            alignment_confidence=0.9)
        self.assertLessEqual(state.adjusted_trust, 1.0)

    def test_trust_never_below_0_1(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.11)
        for _ in range(10):
            state = _ingest(engine, "false_positive")
        self.assertGreaterEqual(state.adjusted_trust, 0.1)

    def test_trust_is_rounded(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.8)
        state = _ingest(engine, "confirmed")
        # rounded to 4 decimal places — verify it's a valid float
        self.assertIsInstance(state.adjusted_trust, float)


# ---------------------------------------------------------------------------
# Tests: replay queue
# ---------------------------------------------------------------------------

class TestReplayQueue(unittest.TestCase):
    """replay_queue_size must grow with each ingest_feedback call."""

    def test_single_ingest_queue_size_one(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "confirmed", record_id="r1")
        self.assertEqual(state.replay_queue_size, 1)

    def test_queue_grows_with_each_call(self) -> None:
        engine = FeedbackLearningEngine()
        for i in range(5):
            state = _ingest(engine, "confirmed", record_id=f"r{i}")
        self.assertEqual(state.replay_queue_size, 5)

    def test_fresh_engine_queue_zero_before_ingest(self) -> None:
        engine = FeedbackLearningEngine()
        self.assertEqual(len(engine.replay_queue), 0)


# ---------------------------------------------------------------------------
# Tests: replay priority
# ---------------------------------------------------------------------------

class TestReplayPriority(unittest.TestCase):
    """replay_priority must escalate for impact tactics or high trust."""

    def test_impact_tactic_gives_high_priority(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.5)
        state = _ingest(engine, "confirmed", tactics=["impact"])
        self.assertEqual(state.replay_priority, "high")

    def test_high_trust_gives_high_priority(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.84)
        state = _ingest(engine, "confirmed", tactics=["collection"],
                        alignment_confidence=0.5)
        # 0.84 + 0.05 = 0.89 >= 0.85 → high
        self.assertEqual(state.replay_priority, "high")

    def test_medium_trust_gives_medium_priority(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.6)
        state = _ingest(engine, "confirmed", tactics=["collection"],
                        alignment_confidence=0.3)
        # 0.6 + 0.05 = 0.65 → medium (< 0.85)
        self.assertEqual(state.replay_priority, "medium")

    def test_low_trust_gives_low_priority(self) -> None:
        engine = FeedbackLearningEngine(initial_trust=0.11)
        # Repeated false-positives drive trust near floor
        for _ in range(8):
            state = _ingest(engine, "false_positive", tactics=["collection"])
        self.assertEqual(state.replay_priority, "low")

    def test_priority_is_one_of_valid_values(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "confirmed")
        self.assertIn(state.replay_priority, {"high", "medium", "low"})


# ---------------------------------------------------------------------------
# Tests: feedback event accumulation
# ---------------------------------------------------------------------------

class TestFeedbackEventAccumulation(unittest.TestCase):
    """feedback_events list must accumulate across calls."""

    def test_single_ingest_adds_one_event(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "confirmed", record_id="r1")
        self.assertEqual(len(state.feedback_events), 1)

    def test_events_accumulate_across_ingests(self) -> None:
        engine = FeedbackLearningEngine()
        for i in range(4):
            state = _ingest(engine, "confirmed", record_id=f"r{i}")
        self.assertEqual(len(state.feedback_events), 4)

    def test_event_analyst_label_recorded(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "malicious")
        self.assertEqual(state.feedback_events[0].analyst_label, "malicious")

    def test_event_trust_delta_is_non_zero(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "confirmed")
        self.assertNotEqual(state.feedback_events[0].trust_delta, 0.0)

    def test_event_record_id_matches(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "confirmed", record_id="specific-id")
        self.assertEqual(state.feedback_events[0].record_id, "specific-id")


# ---------------------------------------------------------------------------
# Tests: field identity and I-15 contract
# ---------------------------------------------------------------------------

class TestFieldIdentityAndContract(unittest.TestCase):
    """record_id/trace_id preserved; to_dict() JSON-serialisable with required keys."""

    def test_record_id_preserved(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "confirmed", record_id="my-rec")
        self.assertEqual(state.record_id, "my-rec")

    def test_trace_id_preserved(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "confirmed", trace_id="t-42")
        self.assertEqual(state.trace_id, "t-42")

    def test_to_dict_is_json_serialisable(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "confirmed")
        json.dumps(state.to_dict())  # must not raise

    def test_to_dict_required_keys(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "confirmed")
        d = state.to_dict()
        required = {
            "record_id", "trace_id", "adjusted_trust",
            "replay_queue_size", "replay_priority", "feedback_events",
        }
        self.assertTrue(required.issubset(d.keys()),
                        f"Missing: {required - d.keys()}")

    def test_feedback_event_to_dict_json_serialisable(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "confirmed")
        for event in state.feedback_events:
            json.dumps(event.to_dict())

    def test_feedback_event_to_dict_required_keys(self) -> None:
        engine = FeedbackLearningEngine()
        state = _ingest(engine, "confirmed")
        d = state.feedback_events[0].to_dict()
        required = {"record_id", "trace_id", "analyst_label", "trust_delta"}
        self.assertTrue(required.issubset(d.keys()),
                        f"Missing: {required - d.keys()}")


if __name__ == "__main__":
    unittest.main()
