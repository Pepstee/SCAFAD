"""
layer1 — SCAFAD Behavioural Intake Zone
========================================

Validates, sanitises, applies privacy controls, and hashes incoming
telemetry. Produces a Layer1ProcessedRecord for downstream layers.

Core modules (WP-3.1..3.5, tested):
  - validation.py          — InputValidationGateway (T-013)
  - preservation.py        — PreservationAssessment (T-014)
  - privacy.py             — PrivacyComplianceFilter (T-015)
  - sanitisation.py        — SanitisationProcessor (T-016)
  - hashing.py             — DeferredHashingManager (T-017)
  - pipeline.py            — Layer1CanonicalPipeline

Extended modules (from scafad-delta, Day 2, T-020):
  - schema.py              — SchemaEvolutionEngine
  - privacy_optimizer.py   — PrivacyUtilityOptimizer (async)
  - semantic_preservation.py — SemanticPreservationOptimizer (async)
  - subsystems/            — audit trail, privacy policy, quality monitor
  - utils/                 — compression, field mapping, hashing utilities
"""

from .pipeline import Layer1CanonicalPipeline, Layer1ProcessedRecord
from .validation import InputValidationGateway
from .preservation import PreservationAssessment, CRITICAL_FIELDS
from .privacy import PrivacyComplianceFilter
from .sanitisation import SanitisationProcessor
from .hashing import DeferredHashingManager

# Extended (scafad-delta) — optional heavy deps degrade gracefully
try:
    from .schema import SchemaEvolutionEngine
except Exception:  # noqa: BLE001
    SchemaEvolutionEngine = None  # type: ignore[assignment,misc]

try:
    from .privacy_optimizer import PrivacyUtilityOptimizer
except Exception:  # noqa: BLE001
    PrivacyUtilityOptimizer = None  # type: ignore[assignment,misc]

try:
    from .semantic_preservation import SemanticPreservationOptimizer, BehavioralFingerprintEngine
except Exception:  # noqa: BLE001
    SemanticPreservationOptimizer = None  # type: ignore[assignment,misc]
    BehavioralFingerprintEngine = None  # type: ignore[assignment,misc]

__all__ = [
    # Core
    "Layer1CanonicalPipeline",
    "Layer1ProcessedRecord",
    "InputValidationGateway",
    "PreservationAssessment",
    "CRITICAL_FIELDS",
    "PrivacyComplianceFilter",
    "SanitisationProcessor",
    "DeferredHashingManager",
    # Extended
    "SchemaEvolutionEngine",
    "PrivacyUtilityOptimizer",
    "SemanticPreservationOptimizer",
    "BehavioralFingerprintEngine",
]
