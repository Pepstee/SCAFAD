"""Layer 3 trust-weighted fusion for the module-split SCAFAD architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from layer2.detection_matrix import DetectionSignal, Layer2DetectionResult


@dataclass
class Layer3FusionResult:
    record_id: str
    trace_id: str
    fused_score: float
    volatility_adjustment: float
    trust_score_input: float
    consensus_strength: float = 0.0
    risk_band: str = "low"
    trust_weights: Dict[str, float] = field(default_factory=dict)
    leading_signals: List[DetectionSignal] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "trace_id": self.trace_id,
            "fused_score": self.fused_score,
            "volatility_adjustment": self.volatility_adjustment,
            "trust_score_input": self.trust_score_input,
            "consensus_strength": self.consensus_strength,
            "risk_band": self.risk_band,
            "trust_weights": dict(self.trust_weights),
            "leading_signals": [signal.to_dict() for signal in self.leading_signals],
        }


class TrustWeightedFusionEngine:
    def __init__(self, base_trust: float = 0.8) -> None:
        self.base_trust = base_trust

    def fuse(self, detection: Layer2DetectionResult) -> Layer3FusionResult:
        if not detection.signals:
            return Layer3FusionResult(
                record_id=detection.record_id,
                trace_id=detection.trace_id,
                fused_score=0.0,
                volatility_adjustment=0.0,
                trust_score_input=0.0,
                consensus_strength=0.0,
                risk_band="low",
            )

        weights: Dict[str, float] = {}
        weighted_total = 0.0
        weight_sum = 0.0
        trust_score_input = float(detection.trust_context.get("trust_score", self.base_trust) or self.base_trust)
        effective_trust = max(0.1, min(1.0, (self.base_trust + trust_score_input) / 2.0))

        for signal in detection.signals:
            weight = max(0.1, min(1.0, effective_trust * signal.confidence))
            weights[signal.detector_name] = round(weight, 4)
            weighted_total += signal.score * weight
            weight_sum += weight

        raw_fused = weighted_total / weight_sum if weight_sum else 0.0
        volatility_adjustment = min(0.15, abs(detection.aggregate_score - raw_fused))
        consensus_boost = min(0.1, detection.detector_consensus * 0.1)
        fused_score = max(0.0, min(1.0, raw_fused - volatility_adjustment + consensus_boost))
        if fused_score >= 0.75:
            risk_band = "high"
        elif fused_score >= 0.3:
            risk_band = "medium"
        else:
            risk_band = "low"

        leading = sorted(detection.signals, key=lambda item: item.score, reverse=True)[:2]
        return Layer3FusionResult(
            record_id=detection.record_id,
            trace_id=detection.trace_id,
            fused_score=round(fused_score, 4),
            volatility_adjustment=round(volatility_adjustment, 4),
            trust_score_input=round(trust_score_input, 4),
            consensus_strength=detection.detector_consensus,
            risk_band=risk_band,
            trust_weights=weights,
            leading_signals=leading,
        )


__all__ = ["Layer3FusionResult", "TrustWeightedFusionEngine"]

