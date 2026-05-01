"""
layer2 — SCAFAD Multi-Vector Detection Matrix
==============================================

Runs 26 parallel detectors over a Layer 1 record and emits detection
signals with per-detector confidence scores.

Public API
----------
  MultiVectorDetectionMatrix  — top-level L2 orchestrator (WP-3.6)
  Layer2DetectionResult       — output dataclass
  DetectionSignal             — per-detector signal dataclass
"""

from .detection_matrix import MultiVectorDetectionMatrix, Layer2DetectionResult, DetectionSignal

__all__ = ["MultiVectorDetectionMatrix", "Layer2DetectionResult", "DetectionSignal"]
