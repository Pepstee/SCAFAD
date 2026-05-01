"""
layers/layer1/preservation.py
==============================

Preservation scoring for the L1 Behavioural Intake Zone.

WP-3.2 / DL-029
=================

Operationalises DL-011: the preservation score is the fraction of
L0-flagged anomaly-critical fields whose value survives all Layer 1
transforms with semantic equality.

Public API
----------
``CRITICAL_FIELDS``
    Frozenset of fully-qualified field paths that carry anomaly signal.

``PreservationAssessment``
    Dataclass holding the score, at-risk field list, and recommendations.

``assess_preservation(original, processed) -> PreservationAssessment``
    Single-pass comparison; never raises (fail-open on malformed input).

Semantic equality rules
-----------------------
- Numeric (int/float)  : ``abs(a - b) <= _EPSILON`` (default 1e-9).
- Boolean              : ``a == b`` (strict; True and 1 are not equal here
                          because fallback_mode is explicitly a flag).
- String               : ``a == b`` (anomaly-critical strings are never
                          sanitised, so identity is the correct check).
- None                 : ``a is None and b is None``.
- Missing in processed : treated as lost → at risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Epsilon for numeric comparisons
# ---------------------------------------------------------------------------
_EPSILON: float = 1e-9

# ---------------------------------------------------------------------------
# Critical field registry
# Each entry is (fully_qualified_path, parent_key_or_None, child_key)
# ---------------------------------------------------------------------------

#: Frozenset of dotted field paths that carry L0 anomaly signal.
#: Used by tests and by the scoring loop.
CRITICAL_FIELDS: frozenset = frozenset({
    # Top-level fields
    "execution_phase",
    "anomaly_type",
    # Telemetry sub-fields (anomaly signal carriers)
    "telemetry_data.l0_duration_ms",
    "telemetry_data.l0_memory_spike_kb",
    "telemetry_data.l0_cpu_utilization",
    "telemetry_data.l0_network_io_bytes",
    "telemetry_data.l0_fallback_mode",
    # Context metadata score fields
    "context_metadata.adversarial_score",
    "context_metadata.economic_risk_score",
})

# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------

@dataclass
class PreservationAssessment:
    """Result of a preservation scoring pass.

    Attributes
    ----------
    preservation_score:
        Float in [0, 1].  1.0 = all critical fields intact.
    at_risk_fields:
        Sorted list of dotted field paths whose value changed or was lost.
    recommendations:
        Human-readable strings explaining what to investigate.
    """

    preservation_score: float
    at_risk_fields: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preservation_score": self.preservation_score,
            "at_risk_fields": list(self.at_risk_fields),
            "recommendations": list(self.recommendations),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve(record: Dict[str, Any], path: str) -> Tuple[bool, Any]:
    """Return (found, value) for a dotted path in *record*.

    Supports exactly one level of nesting (``parent.child``).
    Returns ``(False, None)`` if the path is absent at any level.
    """
    parts = path.split(".", 1)
    if len(parts) == 1:
        if path in record:
            return True, record[path]
        return False, None
    parent_key, child_key = parts
    parent = record.get(parent_key)
    if not isinstance(parent, dict):
        return False, None
    if child_key in parent:
        return True, parent[child_key]
    return False, None


def _semantic_equal(a: Any, b: Any) -> bool:
    """Return True when *a* and *b* are semantically equivalent.

    Numeric types use an absolute epsilon comparison.
    Booleans use strict equality (before the isinstance(bool, int) trap).
    All other types use ``==``.
    """
    # Booleans must be compared first because bool is a subclass of int.
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= _EPSILON
    return a == b


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def assess_preservation(
    original: Optional[Dict[str, Any]],
    processed: Optional[Dict[str, Any]],
) -> PreservationAssessment:
    """Compare *processed* against *original* for anomaly-critical fields.

    Never raises.  Returns a zero-score assessment with a recommendation
    when either argument is not a dict.

    Parameters
    ----------
    original:
        The adapted record dict immediately after the adapter ran, before
        any Layer 1 transforms.
    processed:
        The same record after all transforms (sanitisation, privacy, etc.).

    Returns
    -------
    PreservationAssessment
    """
    # ── Fail-open guard ────────────────────────────────────────────────────
    if not isinstance(original, dict) or not isinstance(processed, dict):
        return PreservationAssessment(
            preservation_score=0.0,
            at_risk_fields=[],
            recommendations=["malformed input: both original and processed must be dicts"],
        )

    # ── Score critical fields only if they exist in original ────────────────
    total = 0
    preserved = 0
    at_risk: List[str] = []

    for path in sorted(CRITICAL_FIELDS):
        orig_found, orig_val = _resolve(original, path)
        if not orig_found:
            # Field not present in original → nothing to preserve; skip
            continue

        total += 1
        proc_found, proc_val = _resolve(processed, path)

        if proc_found and _semantic_equal(orig_val, proc_val):
            preserved += 1
        else:
            at_risk.append(path)

    # ── Compute score ───────────────────────────────────────────────────────
    if total == 0:
        # Nothing scoreable → fail-open
        return PreservationAssessment(
            preservation_score=0.0,
            at_risk_fields=[],
            recommendations=["no critical fields found in original record"],
        )

    score = round(preserved / total, 4)

    # ── Build recommendations ───────────────────────────────────────────────
    recommendations: List[str] = []
    if at_risk:
        recommendations.append(
            f"{len(at_risk)} critical field(s) modified or lost: "
            + ", ".join(at_risk)
        )
        if "anomaly_type" in at_risk:
            recommendations.append(
                "anomaly_type changed — verify classifier output is preserved end-to-end"
            )
        if "execution_phase" in at_risk:
            recommendations.append(
                "execution_phase changed — check phase normalisation in adapter"
            )
        telemetry_at_risk = [f for f in at_risk if f.startswith("telemetry_data.")]
        if telemetry_at_risk:
            recommendations.append(
                "telemetry signal fields affected — sanitisation must not alter numeric metrics"
            )

    return PreservationAssessment(
        preservation_score=score,
        at_risk_fields=at_risk,
        recommendations=recommendations,
    )


__all__ = [
    "CRITICAL_FIELDS",
    "PreservationAssessment",
    "assess_preservation",
]
