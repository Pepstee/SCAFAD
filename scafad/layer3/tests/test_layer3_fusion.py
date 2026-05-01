"""
scafad/layer3/tests/test_layer3_fusion.py
==========================================

T-021 — Layer 3 trust-weighted fusion unit tests.

Covers TrustWeightedFusionEngine.fuse() — the C-2 contribution:
trust-weighted multi-vector fusion of 26 detection signals.

WP: Day-3 (7-day sprint)
"""

from __future__ import annotations

import json
import unittest

from layer2.detection_matrix import DetectionSignal, Layer2DetectionResult
from layer3.trust_fusion import Layer3FusionResult, TrustWeightedFusionEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_detection(
    record_id: str = "rec-001",
    trace_id: str = "trace-001",
    signals: list | None = None,
    aggregate_score: float = 0.0,
    detector_consensus: float = 0.0,
    trust_context: dict | None = None,
) -> Layer2DetectionResult:
    return Layer2DetectionResult(
        record_id=record_id,
        trace_id=trace_id,
        signals=signals or [],
        aggregate_score=aggregate_score,
        detector_consensus=detector_consensus,
        trust_context=trust_context or {},
    )


def _signal(name: str, score: float, confidence: float, rationale: str = "") -> DetectionSignal:
    return DetectionSignal(
        detector_name=name,
        score=score,
        confidence=confidence,
        rationale=rationale or f"{name} signal",
    )


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestEmptySignals(unittest.TestCase):
    """Empty signal list must produce a zero-score low-risk result."""

    def setUp(self) -> None:
        self.engine = TrustWeightedFusionEngine()

    def test_empty_signals_fused_score_zero(self) -> None:
        detection = _make_detection()
        result = self.engine.fuse(detection)
        self.assertEqual(result.fused_score, 0.0)

    def test_empty_signals_risk_band_low(self) -> None:
        detection = _make_detection()
        result = self.engine.fuse(detection)
        self.assertEqual(result.risk_band, "low")

    def test_empty_signals_volatility_zero(self) -> None:
        detection = _make_detection()
        result = self.engine.fuse(detection)
        self.assertEqual(result.volatility_adjustment, 0.0)

    def test_empty_signals_preserves_record_id(self) -> None:
        detection = _make_detection(record_id="my-record")
        result = self.engine.fuse(detection)
        self.assertEqual(result.record_id, "my-record")

    def test_empty_signals_preserves_trace_id(self) -> None:
        detection = _make_detection(trace_id="my-trace")
        result = self.engine.fuse(detection)
        self.assertEqual(result.trace_id, "my-trace")


class TestRiskBandThresholds(unittest.TestCase):
    """fused_score thresholds must map to the correct risk_band."""

    def setUp(self) -> None:
        self.engine = TrustWeightedFusionEngine(base_trust=1.0)

    def _fuse_single(self, score: float, confidence: float = 1.0) -> Layer3FusionResult:
        detection = _make_detection(
            signals=[_signal("d1", score, confidence)],
            aggregate_score=score,
            detector_consensus=0.0,
        )
        return self.engine.fuse(detection)

    def test_high_band_at_0_75(self) -> None:
        result = self._fuse_single(score=0.75, confidence=1.0)
        self.assertEqual(result.risk_band, "high")

    def test_high_band_above_0_75(self) -> None:
        result = self._fuse_single(score=0.9, confidence=1.0)
        self.assertEqual(result.risk_band, "high")

    def test_medium_band_at_0_3(self) -> None:
        # score=0.3, confidence=1.0, base_trust=1.0 → weight=1.0
        # raw_fused=0.3, aggregate=0.3 → volatility=0, consensus_boost=0 → fused=0.3
        result = self._fuse_single(score=0.3, confidence=1.0)
        self.assertEqual(result.risk_band, "medium")

    def test_medium_band_between_0_3_and_0_75(self) -> None:
        result = self._fuse_single(score=0.5, confidence=1.0)
        self.assertEqual(result.risk_band, "medium")

    def test_low_band_below_0_3(self) -> None:
        result = self._fuse_single(score=0.1, confidence=1.0)
        self.assertEqual(result.risk_band, "low")

    def test_low_band_at_zero(self) -> None:
        result = self._fuse_single(score=0.0, confidence=1.0)
        self.assertEqual(result.risk_band, "low")


class TestTrustWeighting(unittest.TestCase):
    """Higher-confidence signals must receive more weight in the fusion."""

    def setUp(self) -> None:
        self.engine = TrustWeightedFusionEngine(base_trust=1.0)

    def test_high_confidence_signal_dominates(self) -> None:
        # Two signals: high-score/high-confidence vs low-score/low-confidence
        signals = [
            _signal("high_conf", score=0.9, confidence=0.9),
            _signal("low_conf", score=0.1, confidence=0.1),
        ]
        detection = _make_detection(
            signals=signals,
            aggregate_score=0.5,
            detector_consensus=0.0,
        )
        result = self.engine.fuse(detection)
        # fused_score should be pulled toward 0.9, well above simple mean 0.5
        self.assertGreater(result.fused_score, 0.5)

    def test_trust_weights_recorded_for_each_signal(self) -> None:
        signals = [
            _signal("det_a", score=0.5, confidence=0.8),
            _signal("det_b", score=0.6, confidence=0.6),
        ]
        detection = _make_detection(signals=signals)
        result = self.engine.fuse(detection)
        self.assertIn("det_a", result.trust_weights)
        self.assertIn("det_b", result.trust_weights)

    def test_higher_confidence_gets_higher_weight(self) -> None:
        signals = [
            _signal("high_conf", score=0.5, confidence=0.9),
            _signal("low_conf", score=0.5, confidence=0.3),
        ]
        detection = _make_detection(signals=signals)
        result = self.engine.fuse(detection)
        self.assertGreater(
            result.trust_weights["high_conf"],
            result.trust_weights["low_conf"],
        )

    def test_single_signal_fused_score_matches_its_score_when_no_volatility(self) -> None:
        # With base_trust=1.0 and trust_context trust_score=1.0:
        # effective_trust=1.0, weight=confidence*1.0
        # raw_fused = score; aggregate_score == score → volatility=0; consensus=0
        score = 0.65
        signals = [_signal("only", score=score, confidence=1.0)]
        detection = _make_detection(
            signals=signals,
            aggregate_score=score,
            detector_consensus=0.0,
            trust_context={"trust_score": 1.0},
        )
        result = self.engine.fuse(detection)
        self.assertAlmostEqual(result.fused_score, score, places=3)


class TestVolatilityAdjustment(unittest.TestCase):
    """Volatility adjustment must reduce fused_score when raw diverges from aggregate."""

    def setUp(self) -> None:
        self.engine = TrustWeightedFusionEngine(base_trust=1.0)

    def test_zero_volatility_when_aggregate_matches_raw(self) -> None:
        score = 0.5
        signals = [_signal("d", score=score, confidence=1.0)]
        detection = _make_detection(
            signals=signals,
            aggregate_score=score,  # identical → no volatility
            detector_consensus=0.0,
            trust_context={"trust_score": 1.0},
        )
        result = self.engine.fuse(detection)
        self.assertEqual(result.volatility_adjustment, 0.0)

    def test_nonzero_volatility_when_aggregate_differs_from_raw(self) -> None:
        signals = [_signal("d", score=0.8, confidence=1.0)]
        detection = _make_detection(
            signals=signals,
            aggregate_score=0.2,  # large gap → volatility > 0
            detector_consensus=0.0,
            trust_context={"trust_score": 1.0},
        )
        result = self.engine.fuse(detection)
        self.assertGreater(result.volatility_adjustment, 0.0)

    def test_volatility_capped_at_0_15(self) -> None:
        signals = [_signal("d", score=1.0, confidence=1.0)]
        detection = _make_detection(
            signals=signals,
            aggregate_score=0.0,  # maximum possible gap
            detector_consensus=0.0,
            trust_context={"trust_score": 1.0},
        )
        result = self.engine.fuse(detection)
        self.assertLessEqual(result.volatility_adjustment, 0.15)

    def test_volatility_lowers_fused_score(self) -> None:
        # base case: no volatility
        signals_a = [_signal("d", score=0.8, confidence=1.0)]
        det_no_vol = _make_detection(
            signals=signals_a,
            aggregate_score=0.8,
            trust_context={"trust_score": 1.0},
        )
        no_vol_result = self.engine.fuse(det_no_vol)

        # with volatility (aggregate diverges)
        signals_b = [_signal("d", score=0.8, confidence=1.0)]
        det_with_vol = _make_detection(
            signals=signals_b,
            aggregate_score=0.3,  # diverges → volatility applied
            trust_context={"trust_score": 1.0},
        )
        with_vol_result = self.engine.fuse(det_with_vol)

        self.assertLess(with_vol_result.fused_score, no_vol_result.fused_score)


class TestConsensusBoost(unittest.TestCase):
    """High detector_consensus must boost the fused_score."""

    def setUp(self) -> None:
        self.engine = TrustWeightedFusionEngine(base_trust=1.0)

    def test_consensus_boost_increases_fused_score(self) -> None:
        signals = [_signal("d", score=0.5, confidence=1.0)]

        no_consensus = _make_detection(
            signals=signals,
            aggregate_score=0.5,
            detector_consensus=0.0,
            trust_context={"trust_score": 1.0},
        )
        high_consensus = _make_detection(
            signals=signals,
            aggregate_score=0.5,
            detector_consensus=1.0,
            trust_context={"trust_score": 1.0},
        )
        no_cons_result = self.engine.fuse(no_consensus)
        hi_cons_result = self.engine.fuse(high_consensus)
        self.assertGreater(hi_cons_result.fused_score, no_cons_result.fused_score)

    def test_consensus_boost_capped_at_0_1(self) -> None:
        # Even with consensus=100 (beyond range), boost must not exceed 0.1
        signals = [_signal("d", score=0.0, confidence=1.0)]
        detection = _make_detection(
            signals=signals,
            aggregate_score=0.0,
            detector_consensus=100.0,
            trust_context={"trust_score": 1.0},
        )
        result = self.engine.fuse(detection)
        # fused_score = 0.0 + min(0.1, 100*0.1=10 → capped 0.1) = 0.1
        self.assertLessEqual(result.fused_score, 0.1 + 1e-9)

    def test_consensus_strength_recorded(self) -> None:
        signals = [_signal("d", score=0.5, confidence=0.7)]
        detection = _make_detection(
            signals=signals,
            detector_consensus=0.75,
        )
        result = self.engine.fuse(detection)
        self.assertAlmostEqual(result.consensus_strength, 0.75, places=5)


class TestLeadingSignals(unittest.TestCase):
    """leading_signals must contain at most the top 2 signals by score."""

    def setUp(self) -> None:
        self.engine = TrustWeightedFusionEngine()

    def test_leading_signals_at_most_two(self) -> None:
        signals = [
            _signal("d1", score=0.9, confidence=0.8),
            _signal("d2", score=0.5, confidence=0.7),
            _signal("d3", score=0.3, confidence=0.6),
            _signal("d4", score=0.1, confidence=0.5),
        ]
        detection = _make_detection(signals=signals)
        result = self.engine.fuse(detection)
        self.assertLessEqual(len(result.leading_signals), 2)

    def test_leading_signals_are_top_two_by_score(self) -> None:
        signals = [
            _signal("d1", score=0.9, confidence=0.8),
            _signal("d2", score=0.7, confidence=0.7),
            _signal("d3", score=0.2, confidence=0.9),
        ]
        detection = _make_detection(signals=signals)
        result = self.engine.fuse(detection)
        names = {s.detector_name for s in result.leading_signals}
        self.assertIn("d1", names)
        self.assertIn("d2", names)
        self.assertNotIn("d3", names)

    def test_single_signal_gives_one_leading_signal(self) -> None:
        signals = [_signal("only", score=0.6, confidence=0.8)]
        detection = _make_detection(signals=signals)
        result = self.engine.fuse(detection)
        self.assertEqual(len(result.leading_signals), 1)

    def test_leading_signals_ordered_descending(self) -> None:
        signals = [
            _signal("low", score=0.2, confidence=0.8),
            _signal("high", score=0.9, confidence=0.8),
        ]
        detection = _make_detection(signals=signals)
        result = self.engine.fuse(detection)
        if len(result.leading_signals) == 2:
            self.assertGreaterEqual(
                result.leading_signals[0].score,
                result.leading_signals[1].score,
            )


class TestTrustContextPropagation(unittest.TestCase):
    """trust_score from trust_context must be reflected in trust_score_input."""

    def setUp(self) -> None:
        self.engine = TrustWeightedFusionEngine(base_trust=0.8)

    def test_trust_score_input_from_context(self) -> None:
        signals = [_signal("d", score=0.5, confidence=0.7)]
        detection = _make_detection(
            signals=signals,
            trust_context={"trust_score": 0.6},
        )
        result = self.engine.fuse(detection)
        self.assertAlmostEqual(result.trust_score_input, 0.6, places=4)

    def test_missing_trust_score_falls_back_to_base_trust(self) -> None:
        signals = [_signal("d", score=0.5, confidence=0.7)]
        detection = _make_detection(signals=signals, trust_context={})
        result = self.engine.fuse(detection)
        # base_trust=0.8 used when context has no trust_score
        self.assertAlmostEqual(result.trust_score_input, 0.8, places=4)

    def test_low_trust_reduces_effective_weights(self) -> None:
        engine_low = TrustWeightedFusionEngine(base_trust=0.2)
        engine_high = TrustWeightedFusionEngine(base_trust=1.0)
        signals = [_signal("d", score=0.5, confidence=0.8)]
        det = _make_detection(signals=signals, aggregate_score=0.5,
                              trust_context={"trust_score": 0.2})
        det_high = _make_detection(signals=signals, aggregate_score=0.5,
                                   trust_context={"trust_score": 1.0})
        low_w = engine_low.fuse(det).trust_weights["d"]
        high_w = engine_high.fuse(det_high).trust_weights["d"]
        self.assertLess(low_w, high_w)


class TestFusionResultToDict(unittest.TestCase):
    """to_dict() must return a JSON-serialisable dict with required keys."""

    def setUp(self) -> None:
        self.engine = TrustWeightedFusionEngine()

    def test_to_dict_is_json_serialisable(self) -> None:
        signals = [_signal("d1", score=0.6, confidence=0.8)]
        detection = _make_detection(signals=signals, aggregate_score=0.6)
        result = self.engine.fuse(detection)
        json.dumps(result.to_dict())  # must not raise

    def test_to_dict_contains_required_keys(self) -> None:
        signals = [_signal("d1", score=0.6, confidence=0.8)]
        detection = _make_detection(signals=signals)
        result = self.engine.fuse(detection)
        d = result.to_dict()
        required = {
            "record_id", "trace_id", "fused_score", "volatility_adjustment",
            "trust_score_input", "consensus_strength", "risk_band",
            "trust_weights", "leading_signals",
        }
        self.assertTrue(required.issubset(d.keys()),
                        f"Missing keys: {required - d.keys()}")

    def test_to_dict_fused_score_is_float(self) -> None:
        signals = [_signal("d", score=0.5, confidence=0.7)]
        detection = _make_detection(signals=signals)
        d = self.engine.fuse(detection).to_dict()
        self.assertIsInstance(d["fused_score"], float)

    def test_to_dict_leading_signals_is_list(self) -> None:
        signals = [_signal("d", score=0.5, confidence=0.7)]
        detection = _make_detection(signals=signals)
        d = self.engine.fuse(detection).to_dict()
        self.assertIsInstance(d["leading_signals"], list)

    def test_to_dict_empty_signals_still_valid(self) -> None:
        detection = _make_detection()
        d = self.engine.fuse(detection).to_dict()
        json.dumps(d)


class TestFusedScoreBounds(unittest.TestCase):
    """fused_score must always be in [0.0, 1.0]."""

    def setUp(self) -> None:
        self.engine = TrustWeightedFusionEngine()

    def test_fused_score_never_negative(self) -> None:
        signals = [_signal("d", score=0.0, confidence=0.1)]
        detection = _make_detection(
            signals=signals,
            aggregate_score=1.0,  # large gap → maximum volatility applied
        )
        result = self.engine.fuse(detection)
        self.assertGreaterEqual(result.fused_score, 0.0)

    def test_fused_score_never_above_one(self) -> None:
        signals = [_signal("d", score=1.0, confidence=1.0)]
        detection = _make_detection(
            signals=signals,
            aggregate_score=1.0,
            detector_consensus=100.0,  # huge consensus boost attempt
            trust_context={"trust_score": 1.0},
        )
        result = self.engine.fuse(detection)
        self.assertLessEqual(result.fused_score, 1.0)

    def test_multiple_signals_score_in_range(self) -> None:
        signals = [
            _signal(f"d{i}", score=float(i) / 10.0, confidence=0.5 + float(i) * 0.04)
            for i in range(10)
        ]
        detection = _make_detection(
            signals=signals,
            aggregate_score=0.45,
            detector_consensus=0.5,
        )
        result = self.engine.fuse(detection)
        self.assertGreaterEqual(result.fused_score, 0.0)
        self.assertLessEqual(result.fused_score, 1.0)


if __name__ == "__main__":
    unittest.main()
