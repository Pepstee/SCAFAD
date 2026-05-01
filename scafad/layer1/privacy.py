"""
layers/layer1/privacy.py
=========================

Privacy compliance filter for the L1 Behavioural Intake Zone.

WP-3.3 / DL-030
=================

``PrivacyComplianceFilter`` enforces GDPR / CCPA / HIPAA field-pattern
rules using a regex-only pattern bank.  No ML dependency.

Key rule: a redaction never removes an anomaly-critical field.
If a critical field contains a PII pattern it is hash-pseudonymised
(SHA-256 hex) rather than stripped.

Public API
----------
``PrivacyRegime``           — Enum: GDPR | CCPA | HIPAA
``RedactionAction``         — Dataclass: field_path, action, pattern_matched, regime
``RedactionResult``         — Dataclass: filtered_record, actions_taken
``PrivacyComplianceFilter`` — .apply(record, regime=GDPR) → RedactionResult
"""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Critical fields (imported from preservation to avoid duplication)
# ---------------------------------------------------------------------------
from .preservation import CRITICAL_FIELDS as _CRITICAL_FIELDS

# ---------------------------------------------------------------------------
# Regime enum
# ---------------------------------------------------------------------------

class PrivacyRegime(Enum):
    GDPR  = "gdpr"
    CCPA  = "ccpa"
    HIPAA = "hipaa"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RedactionAction:
    """Records a single redaction or pseudonymisation event."""

    field_path: str       # dotted path, e.g. "context_metadata.user_email"
    action: str           # "redacted" | "pseudonymised"
    pattern_matched: str  # e.g. "email", "ssn", "credit_card"
    regime: str           # regime name that triggered this action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_path": self.field_path,
            "action": self.action,
            "pattern_matched": self.pattern_matched,
            "regime": self.regime,
        }


@dataclass
class RedactionResult:
    """Output of a single filter pass."""

    filtered_record: Dict[str, Any]
    actions_taken: List[RedactionAction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filtered_record": copy.deepcopy(self.filtered_record),
            "actions_taken": [a.to_dict() for a in self.actions_taken],
        }


# ---------------------------------------------------------------------------
# Pattern bank
# ---------------------------------------------------------------------------

# Email
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE
)

# Phone — require explicit structure to avoid matching IP addresses and
# UUID digit-segments.  Supports international (+CC ...) and common
# national formats (NXX-NXX-XXXX, NXX NXX XXXX, 07XX XXXXXX).
_PHONE_RE = re.compile(
    r"(?:"
    r"\+\d{1,3}[\s\-]?\d[\d\s\-]{6,12}\d"
    r"|\b\d{3}[\s\-]\d{3}[\s\-]\d{4}\b"
    r"|\b\d{4}[\s\-]\d{6}\b"
    r")"
)

# SSN (US) — 000-00-0000 format
_SSN_RE = re.compile(
    r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"
)

# IPv4
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

# IPv6 (full or compressed)
_IPV6_RE = re.compile(
    r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,7}:"
    r"|:(?::[0-9a-fA-F]{1,4}){1,7}"
    r"|::(?:[fF]{4}:){0,1}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)){3}"
)

# IBAN — 2 letters + 2 digits + 8-30 alphanumeric
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{8,30}\b")

# ICD-10 — decimal form required (e.g. J18.9, Z23.0) — bare codes excluded to reduce false positives
_ICD10_RE = re.compile(r"\b[A-Z]\d{2}\.\d{1,4}\b")

# NHS number — 10 digits (may be spaced as 3 3 4)
_NHS_RE = re.compile(r"\b\d{3}[\s\-]?\d{3}[\s\-]?\d{4}\b")

# Date of birth patterns — YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
_DOB_RE = re.compile(
    r"\b(?:19|20)\d{2}[-/]\d{2}[-/]\d{2}\b"
    r"|\b\d{2}[-/]\d{2}[-/](?:19|20)\d{2}\b"
)

# Credit-card — 13-19 digits (spaces/hyphens allowed between groups)
_CC_DIGITS_RE = re.compile(
    r"\b(?:\d[ \-]?){13,18}\d\b"
)


# ---------------------------------------------------------------------------
# Luhn check
# ---------------------------------------------------------------------------

def _luhn_valid(number: str) -> bool:
    """Return True when *number* (digits only) passes the Luhn check."""
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# ---------------------------------------------------------------------------
# Regime -> pattern set mapping
# ---------------------------------------------------------------------------

# Each entry: (pattern_name, compiled_regex, optional_validator)
_GDPR_PATTERNS: List[Tuple[str, re.Pattern, Optional[Any]]] = [
    ("email",       _EMAIL_RE,  None),
    ("phone",       _PHONE_RE,  None),
    ("ssn",         _SSN_RE,    None),
    ("credit_card", _CC_DIGITS_RE, lambda m: _luhn_valid(re.sub(r"\D", "", m))),
    ("ipv4",        _IPV4_RE,   None),
    ("ipv6",        _IPV6_RE,   None),
    ("iban",        _IBAN_RE,   None),
    ("dob",         _DOB_RE,    None),
    ("nhs",         _NHS_RE,    None),
]

_CCPA_PATTERNS: List[Tuple[str, re.Pattern, Optional[Any]]] = _GDPR_PATTERNS

_HIPAA_PATTERNS: List[Tuple[str, re.Pattern, Optional[Any]]] = [
    ("email",       _EMAIL_RE,  None),
    ("ssn",         _SSN_RE,    None),
    ("icd10",       _ICD10_RE,  None),
    ("nhs",         _NHS_RE,    None),
    ("dob",         _DOB_RE,    None),
    ("credit_card", _CC_DIGITS_RE, lambda m: _luhn_valid(re.sub(r"\D", "", m))),
]

_REGIME_PATTERNS = {
    PrivacyRegime.GDPR:  _GDPR_PATTERNS,
    PrivacyRegime.CCPA:  _CCPA_PATTERNS,
    PrivacyRegime.HIPAA: _HIPAA_PATTERNS,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_critical(field_path: str) -> bool:
    return field_path in _CRITICAL_FIELDS


def _scan_string(
    value: str,
    field_path: str,
    regime: PrivacyRegime,
    patterns: List[Tuple[str, re.Pattern, Optional[Any]]],
) -> Tuple[str, List[RedactionAction]]:
    """Scan *value* for PII patterns; return (new_value, actions)."""
    actions: List[RedactionAction] = []
    new_value = value
    critical = _is_critical(field_path)

    for pattern_name, regex, validator in patterns:
        matches = list(regex.finditer(new_value))
        for m in matches:
            raw = m.group(0)
            if validator is not None and not validator(raw):
                continue
            if critical:
                replacement = f"[PSEUDO:{_sha256_hex(raw)[:16]}]"
                act = "pseudonymised"
            else:
                replacement = f"[REDACTED_{pattern_name.upper()}]"
                act = "redacted"
            new_value = new_value.replace(raw, replacement, 1)
            actions.append(RedactionAction(
                field_path=field_path,
                action=act,
                pattern_matched=pattern_name,
                regime=regime.value,
            ))
    return new_value, actions


def _scan_key_name(
    key: str,
    field_path: str,
    regime: PrivacyRegime,
    patterns: List[Tuple[str, re.Pattern, Optional[Any]]],
) -> Optional[str]:
    """Return the pattern name if the key name itself signals PII, else None."""
    _KEY_SIGNALS = {
        "email": re.compile(r"email|e_mail", re.I),
        "phone": re.compile(r"phone|mobile|tel\b", re.I),
        "ssn":   re.compile(r"\bssn\b|social.?security", re.I),
        "dob":   re.compile(r"\bdob\b|date.?of.?birth|birth.?date", re.I),
        "nhs":   re.compile(r"\bnhs\b", re.I),
    }
    for pname, sig_re in _KEY_SIGNALS.items():
        if any(p[0] == pname for p in patterns) and sig_re.search(key):
            return pname
    return None


def _process_mapping(
    mapping: Dict[str, Any],
    parent_path: str,
    regime: PrivacyRegime,
    patterns: List[Tuple[str, re.Pattern, Optional[Any]]],
) -> Tuple[Dict[str, Any], List[RedactionAction]]:
    """Recursively scan *mapping* and return a cleaned copy + actions."""
    result: Dict[str, Any] = {}
    actions: List[RedactionAction] = []

    for key, value in mapping.items():
        fq = f"{parent_path}.{key}" if parent_path else key
        critical = _is_critical(fq)

        sig = _scan_key_name(key, fq, regime, patterns)
        if sig is not None and isinstance(value, str) and value.strip():
            if critical:
                result[key] = f"[PSEUDO:{_sha256_hex(value)[:16]}]"
                act = "pseudonymised"
            else:
                result[key] = "[REDACTED]"
                act = "redacted"
            actions.append(RedactionAction(
                field_path=fq,
                action=act,
                pattern_matched=sig,
                regime=regime.value,
            ))
            continue

        if isinstance(value, dict):
            cleaned, sub_actions = _process_mapping(value, fq, regime, patterns)
            result[key] = cleaned
            actions.extend(sub_actions)
        elif isinstance(value, str):
            new_val, val_actions = _scan_string(value, fq, regime, patterns)
            result[key] = new_val
            actions.extend(val_actions)
        else:
            result[key] = value

    return result, actions


# ---------------------------------------------------------------------------
# Public filter class
# ---------------------------------------------------------------------------

class PrivacyComplianceFilter:
    """Apply per-regime PII redaction to an adapted L1 record.

    Usage::

        f = PrivacyComplianceFilter()
        result = f.apply(record, regime=PrivacyRegime.GDPR)

    The filter operates on a deep copy of *record*; the original is never
    mutated.  Anomaly-critical fields are hash-pseudonymised rather than
    stripped.  Unknown / non-dict inputs return a fail-open empty result.
    """

    def apply(
        self,
        record: Any,
        regime: PrivacyRegime = PrivacyRegime.GDPR,
    ) -> RedactionResult:
        """Apply the privacy filter and return a RedactionResult."""
        if not isinstance(record, dict):
            return RedactionResult(filtered_record={}, actions_taken=[])

        patterns = _REGIME_PATTERNS.get(regime, _GDPR_PATTERNS)
        working = copy.deepcopy(record)
        all_actions: List[RedactionAction] = []

        cleaned_top, top_actions = _process_mapping(
            working, "", regime, patterns
        )
        all_actions.extend(top_actions)

        return RedactionResult(
            filtered_record=cleaned_top,
            actions_taken=all_actions,
        )


__all__ = [
    "PrivacyRegime",
    "RedactionAction",
    "RedactionResult",
    "PrivacyComplianceFilter",
]
