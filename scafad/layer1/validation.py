"""
layers/layer1/validation.py
============================

InputValidationGateway — WP-3.1 / DL-028
==========================================

Replaces the stub ``_validate_shape`` in ``Layer1CanonicalPipeline`` with an
accumulating, structured validation pass.

Contract
--------
``InputValidationGateway.validate(record: Dict[str, Any]) -> ValidationResult``

- Accumulates *all* errors in a single pass (never raises; caller decides).
- Returns ``ValidationResult(valid=True, errors=[])`` on a clean record.
- Returns ``ValidationResult(valid=False, errors=[...])`` otherwise.

Rules enforced
--------------
1. Required fields present and non-empty.
2. Type checks: record_id/function_name/execution_phase/anomaly_type/
   schema_version must be ``str``; timestamp must be numeric (int or float);
   telemetry_data must be ``dict``.
3. Enum values: execution_phase in allowed set; anomaly_type in allowed set.
4. String length caps: function_name <= 256, schema_version <= 32,
   record_id <= 128.
5. Numeric bounds on context_metadata score fields (all in [0, 1]) and on
   telemetry_data metric fields (duration/memory/network >= 0;
   cpu_utilization in [0, 100]).
6. Conditional requirement: ``error_message`` must be present and non-empty
   when ``execution_phase == 'error'``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# L1 allowed enum values (post-adapter normalisation)
# ---------------------------------------------------------------------------
_ALLOWED_EXECUTION_PHASES = frozenset({
    "initialization", "execution", "completion", "error", "timeout",
})
_ALLOWED_ANOMALY_TYPES = frozenset({
    "benign", "suspicious", "malicious", "unknown",
})

# ---------------------------------------------------------------------------
# Required top-level fields with their expected Python types
# ---------------------------------------------------------------------------
_NUMERIC = (int, float)

_REQUIRED_FIELDS: Dict[str, Union[type, Tuple[type, ...]]] = {
    "record_id":       str,
    "timestamp":       _NUMERIC,
    "function_name":   str,
    "execution_phase": str,
    "anomaly_type":    str,
    "telemetry_data":  dict,
    "schema_version":  str,
}

# ---------------------------------------------------------------------------
# String length caps
# ---------------------------------------------------------------------------
_STRING_LENGTH_CAPS: Dict[str, int] = {
    "function_name": 256,
    "schema_version": 32,
    "record_id": 128,
}

# ---------------------------------------------------------------------------
# Numeric bounds: field_path -> (min_inclusive, max_inclusive)
# None means unbounded in that direction.
# ---------------------------------------------------------------------------
_SCORE_BOUNDS: Dict[str, Tuple[Optional[float], Optional[float]]] = {
    "context_metadata.completeness_score":        (0.0, 1.0),
    "context_metadata.adversarial_score":         (0.0, 1.0),
    "context_metadata.economic_risk_score":       (0.0, 1.0),
    "context_metadata.silent_failure_probability": (0.0, 1.0),
    "context_metadata.confidence_level":          (0.0, 1.0),
    "context_metadata.data_quality_score":        (0.0, 1.0),
    "context_metadata.anomaly_severity":          (0,   10),
}

_TELEMETRY_BOUNDS: Dict[str, Tuple[Optional[float], Optional[float]]] = {
    "telemetry_data.l0_duration_ms":       (0.0,  None),
    "telemetry_data.l0_memory_spike_kb":   (0,    None),
    "telemetry_data.l0_cpu_utilization":   (0.0, 100.0),
    "telemetry_data.l0_network_io_bytes":  (0,    None),
    "telemetry_data.l0_payload_size_bytes": (0,   None),
}


# ---------------------------------------------------------------------------
# Public data-classes
# ---------------------------------------------------------------------------

@dataclass
class ValidationError:
    """A single validation failure."""

    field: str
    message: str
    value: Any = None

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


@dataclass
class ValidationResult:
    """Return value of ``InputValidationGateway.validate``."""

    valid: bool
    errors: List[ValidationError] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid

    def error_fields(self) -> List[str]:
        """Convenience: list of field names that produced an error."""
        return [e.field for e in self.errors]


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

class InputValidationGateway:
    """Validates an adapted Layer 1 record dict against the L1 schema contract.

    Per WP-3.1 / DL-028.  Accumulates all errors in a single pass rather than
    raising on the first failure, so callers receive the complete error picture.

    Usage::

        gw = InputValidationGateway()
        result = gw.validate(adapted_record)
        if not result.valid:
            raise ValueError('; '.join(str(e) for e in result.errors))
    """

    def validate(self, record: Dict[str, Any]) -> ValidationResult:
        """Validate *record* and return a :class:`ValidationResult`.

        Never raises; all problems are captured in the returned object.
        """
        errors: List[ValidationError] = []

        if not isinstance(record, dict):
            errors.append(ValidationError("record", "must be a dict", record))
            return ValidationResult(valid=False, errors=errors)

        self._check_required_fields(record, errors)
        self._check_types(record, errors)
        self._check_enum_values(record, errors)
        self._check_string_lengths(record, errors)
        self._check_numeric_bounds(record, errors)
        self._check_conditional_requirements(record, errors)

        return ValidationResult(valid=not errors, errors=errors)

    # ------------------------------------------------------------------
    # Private checks — each appends to *errors* in-place
    # ------------------------------------------------------------------

    def _check_required_fields(
        self, record: Dict[str, Any], errors: List[ValidationError]
    ) -> None:
        for fname in _REQUIRED_FIELDS:
            value = record.get(fname)
            if value is None:
                errors.append(
                    ValidationError(fname, "required field is missing or null", value)
                )
            elif isinstance(value, str) and not value.strip():
                errors.append(
                    ValidationError(
                        fname, "required string field must not be empty", value
                    )
                )

    def _check_types(
        self, record: Dict[str, Any], errors: List[ValidationError]
    ) -> None:
        for fname, expected in _REQUIRED_FIELDS.items():
            value = record.get(fname)
            if value is None:
                continue  # already reported above
            if not isinstance(value, expected):
                if isinstance(expected, tuple):
                    expected_label = " or ".join(t.__name__ for t in expected)
                else:
                    expected_label = expected.__name__
                errors.append(
                    ValidationError(
                        fname,
                        f"expected {expected_label}, got {type(value).__name__}",
                        value,
                    )
                )

    def _check_enum_values(
        self, record: Dict[str, Any], errors: List[ValidationError]
    ) -> None:
        phase = record.get("execution_phase")
        if isinstance(phase, str) and phase and phase not in _ALLOWED_EXECUTION_PHASES:
            errors.append(
                ValidationError(
                    "execution_phase",
                    f"must be one of {sorted(_ALLOWED_EXECUTION_PHASES)}, "
                    f"got '{phase}'",
                    phase,
                )
            )

        anomaly = record.get("anomaly_type")
        if isinstance(anomaly, str) and anomaly and anomaly not in _ALLOWED_ANOMALY_TYPES:
            errors.append(
                ValidationError(
                    "anomaly_type",
                    f"must be one of {sorted(_ALLOWED_ANOMALY_TYPES)}, "
                    f"got '{anomaly}'",
                    anomaly,
                )
            )

    def _check_string_lengths(
        self, record: Dict[str, Any], errors: List[ValidationError]
    ) -> None:
        for fname, max_len in _STRING_LENGTH_CAPS.items():
            value = record.get(fname)
            if isinstance(value, str) and len(value) > max_len:
                errors.append(
                    ValidationError(
                        fname,
                        f"exceeds max length {max_len} (got {len(value)})",
                        len(value),
                    )
                )

    def _check_numeric_bounds(
        self, record: Dict[str, Any], errors: List[ValidationError]
    ) -> None:
        all_bounds = {**_SCORE_BOUNDS, **_TELEMETRY_BOUNDS}
        for field_path, (lo, hi) in all_bounds.items():
            parts = field_path.split(".", 1)
            if len(parts) == 2:
                parent_key, child_key = parts
                parent = record.get(parent_key)
                if not isinstance(parent, dict):
                    continue
                value = parent.get(child_key)
            else:
                value = record.get(field_path)

            if value is None or not isinstance(value, (int, float)):
                continue

            if lo is not None and value < lo:
                errors.append(
                    ValidationError(
                        field_path, f"must be >= {lo}, got {value}", value
                    )
                )
            if hi is not None and value > hi:
                errors.append(
                    ValidationError(
                        field_path, f"must be <= {hi}, got {value}", value
                    )
                )

    def _check_conditional_requirements(
        self, record: Dict[str, Any], errors: List[ValidationError]
    ) -> None:
        phase = record.get("execution_phase")
        if phase == "error":
            msg = record.get("error_message")
            if not msg or (isinstance(msg, str) and not msg.strip()):
                errors.append(
                    ValidationError(
                        "error_message",
                        "required when execution_phase is 'error'",
                        msg,
                    )
                )


__all__ = [
    "ValidationError",
    "ValidationResult",
    "InputValidationGateway",
]
