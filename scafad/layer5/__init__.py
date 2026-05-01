"""
layer5 — SCAFAD Threat Alignment (MITRE ATT&CK)
================================================

Maps the decision trace to MITRE ATT&CK tactics and techniques.

Public API
----------
  ThreatAlignmentEngine   — aligns Layer4DecisionTrace → ThreatAlignmentResult
  ThreatAlignmentResult   — output dataclass
"""

from .threat_alignment import ThreatAlignmentEngine, ThreatAlignmentResult

__all__ = ["ThreatAlignmentEngine", "ThreatAlignmentResult"]
