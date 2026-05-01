"""
layer3 — SCAFAD Trust-Weighted Fusion Engine
=============================================

Combines detection signals under a learned trust model (C-2).

Public API
----------
  TrustWeightedFusionEngine  — fuses Layer2DetectionResult → Layer3FusionResult
  Layer3FusionResult         — output dataclass
"""

from .trust_fusion import TrustWeightedFusionEngine, Layer3FusionResult

__all__ = ["TrustWeightedFusionEngine", "Layer3FusionResult"]
