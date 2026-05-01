"""
layer6 — SCAFAD Feedback & Learning Engine
==========================================

Applies analyst labels to modulate detector trust scores.

Public API
----------
  FeedbackLearningEngine  — processes analyst feedback → Layer6FeedbackState
  Layer6FeedbackState     — output dataclass
  FeedbackEvent           — per-analyst-label event dataclass
"""

from .feedback_learning import FeedbackLearningEngine, Layer6FeedbackState, FeedbackEvent

__all__ = ["FeedbackLearningEngine", "Layer6FeedbackState", "FeedbackEvent"]
