"""
layer4 — SCAFAD Explainability & Decision Trace
===============================================

Produces a tiered, budget-controlled rationale (C-4).

Public API
----------
  ExplainabilityDecisionEngine  — builds Layer4DecisionTrace
  Layer4DecisionTrace           — output dataclass
"""

from .explainability import ExplainabilityDecisionEngine, Layer4DecisionTrace

__all__ = ["ExplainabilityDecisionEngine", "Layer4DecisionTrace"]
