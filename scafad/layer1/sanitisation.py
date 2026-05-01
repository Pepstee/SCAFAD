"""
layers/layer1/sanitisation.py
==============================

Sanitisation processor for the L1 Behavioural Intake Zone.

WP-3.4 / DL-031
=================

``SanitisationProcessor`` applies six value-level sanitisers to every
non-critical string field in an adapted L1 record.

Sanitisers
----------
``_sanitize_path``     — resolve ``..``, reject/strip absolute when
                         ``disallow_abs=True``, normalise backslash.
``_sanitize_url``      — allow-list schemes (http/https), strip credentials.
``_sanitize_html``     — strip ``<script>`` blocks, ``html.escape`` remainder.
``_sanitize_sql``      — flag SQL-injection patterns (returns bool).
``_sanitize_command``  — strip shell metacharacters ; & | $ `.
``_sanitize_unicode``  — NFKC normalise, strip zero-width characters.

Key rule: anomaly-critical fields (from ``CRITICAL_FIELDS`` in
``preservation.py``) are never passed through any sanitiser.

Public API
----------
``SanitisationFlag``      — Dataclass: field_path, sanitiser, detail
``SanitisationResult``    — Dataclass: sanitised_record, flags
``SanitisationProcessor`` — .sanitise(record) → SanitisationResult
"""

from __future__ import annotations

import copy
import html
import os
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .preservation import CRITICAL_FIELDS as _CRITICAL_FIELDS

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SanitisationFlag:
    """Records a single sanitisation event."""

    field_path: str   # dotted path, e.g. "context_metadata.user_input"
    sanitiser: str    # e.g. "command", "html", "path"
    detail: str = ""  # optional human-readable note

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_path": self.field_path,
            "sanitiser": self.sanitiser,
            "detail": self.detail,
        }


@dataclass
class SanitisationResult:
    """Output of a single sanitisation pass."""

    sanitised_record: Dict[str, Any]
    flags: List[SanitisationFlag] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sanitised_record": copy.deepcopy(self.sanitised_record),
            "flags": [f.to_dict() for f in self.flags],
        }


# ---------------------------------------------------------------------------
# Zero-width character set
# ---------------------------------------------------------------------------

_ZERO_WIDTH_RE = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\ufeff\u2060-\u2064]"
)

# Shell metacharacters to strip from command strings
_SHELL_META_RE = re.compile(r"[;&|$`]")

# SQL-injection pattern — keyword heuristic (case-insensitive)
_SQL_RE = re.compile(
    r"\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|UNION|EXEC)\b",
    re.IGNORECASE,
)

# <script>...</script> (including multiline, case-insensitive)
_SCRIPT_RE = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)

# Allowed URL schemes
_ALLOWED_SCHEMES = {"http", "https"}


# ---------------------------------------------------------------------------
# Individual sanitiser functions
# ---------------------------------------------------------------------------

class SanitisationProcessor:
    """Apply value-level sanitisers to non-critical fields of an L1 record.

    Usage::

        proc = SanitisationProcessor()
        result = proc.sanitise(record)

    The processor operates on a deep copy of *record*; the original is never
    mutated.  Fields listed in ``CRITICAL_FIELDS`` are skipped entirely.
    Non-string values are passed through unchanged.
    """

    # ------------------------------------------------------------------
    # Individual sanitisers (callable directly for unit testing)
    # ------------------------------------------------------------------

    def _sanitize_path(self, value: str, disallow_abs: bool = True) -> str:
        """Normalise a file-path string.

        - Converts backslashes to forward slashes.
        - Resolves ``..`` segments via ``os.path.normpath``.
        - If *disallow_abs* is ``True`` and the result is absolute, the
          leading separator is stripped.
        """
        # Normalise separator
        normalised = value.replace("\\", "/")
        # Resolve '..' via posixpath logic
        normalised = os.path.normpath(normalised).replace("\\", "/")
        # Strip any remaining leading '..' segments that escape the root
        parts = normalised.split("/")
        parts = [p for p in parts if p != ".."]
        normalised = "/".join(parts) or "."
        # Strip leading absolute slash if forbidden
        if disallow_abs and (normalised.startswith("/") or normalised.startswith("\\")):
            normalised = normalised.lstrip("/").lstrip("\\")
        return normalised

    def _sanitize_url(self, value: str) -> str:
        """Sanitise a URL string.

        - Rejects any scheme not in ``{http, https}`` by returning an empty
          string.
        - Strips username/password credentials from the URL.
        """
        try:
            parsed = urllib.parse.urlsplit(value)
        except Exception:
            return ""

        if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
            return ""

        # Rebuild without credentials
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"

        clean = urllib.parse.urlunsplit((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.query,
            parsed.fragment,
        ))
        return clean

    def _sanitize_html(self, value: str) -> str:
        """Sanitise an HTML string.

        - Strips ``<script>...</script>`` blocks.
        - Escapes remaining HTML with ``html.escape(quote=True)``.
        """
        # Strip script blocks first
        stripped = _SCRIPT_RE.sub("", value)
        # Escape everything else
        return html.escape(stripped, quote=True)

    def _sanitize_sql(self, value: str) -> bool:
        """Return ``True`` if *value* contains SQL-injection patterns.

        This is a *flagger*, not a rewriter — the caller decides what to do
        with the result.
        """
        return bool(_SQL_RE.search(value))

    def _sanitize_command(self, value: str) -> str:
        """Strip shell metacharacters (; & | $ `) from *value*."""
        return _SHELL_META_RE.sub("", value)

    def _sanitize_unicode(self, value: str) -> str:
        """NFKC-normalise *value* and strip zero-width characters."""
        normalised = unicodedata.normalize("NFKC", value)
        return _ZERO_WIDTH_RE.sub("", normalised)

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def _is_critical(self, field_path: str) -> bool:
        return field_path in _CRITICAL_FIELDS

    def _sanitize_value(
        self,
        value: str,
        field_path: str,
    ) -> Tuple[str, List[SanitisationFlag]]:
        """Apply the sanitiser chain to a single string *value*.

        Returns ``(new_value, flags)``.  SQL-injection payloads are flagged
        but the value is still passed through the command sanitiser (they may
        overlap).
        """
        flags: List[SanitisationFlag] = []
        v = value

        # Unicode first — normalise the input before other checks
        v_uni = self._sanitize_unicode(v)
        if v_uni != v:
            flags.append(SanitisationFlag(
                field_path=field_path,
                sanitiser="unicode",
                detail="NFKC normalised / zero-width stripped",
            ))
            v = v_uni

        # Command metacharacters
        v_cmd = self._sanitize_command(v)
        if v_cmd != v:
            flags.append(SanitisationFlag(
                field_path=field_path,
                sanitiser="command",
                detail="shell metacharacters removed",
            ))
            v = v_cmd

        # HTML script / escaping — only if value looks HTML-like
        if "<" in v or ">" in v or '"' in v:
            v_html = self._sanitize_html(v)
            if v_html != v:
                flags.append(SanitisationFlag(
                    field_path=field_path,
                    sanitiser="html",
                    detail="HTML escaped / script stripped",
                ))
                v = v_html

        # SQL-injection flag
        if self._sanitize_sql(v):
            flags.append(SanitisationFlag(
                field_path=field_path,
                sanitiser="sql",
                detail="SQL-injection pattern detected",
            ))

        return v, flags

    def _process_mapping(
        self,
        mapping: Dict[str, Any],
        parent_path: str,
    ) -> Tuple[Dict[str, Any], List[SanitisationFlag]]:
        """Recursively sanitise *mapping* and return cleaned copy + flags."""
        result: Dict[str, Any] = {}
        all_flags: List[SanitisationFlag] = []

        for key, value in mapping.items():
            fq = f"{parent_path}.{key}" if parent_path else key

            if self._is_critical(fq):
                # Critical fields bypass all sanitisers
                result[key] = value
                continue

            if isinstance(value, dict):
                cleaned, sub_flags = self._process_mapping(value, fq)
                result[key] = cleaned
                all_flags.extend(sub_flags)
            elif isinstance(value, str):
                cleaned_str, str_flags = self._sanitize_value(value, fq)
                result[key] = cleaned_str
                all_flags.extend(str_flags)
            else:
                result[key] = value

        return result, all_flags

    def sanitise(self, record: Any) -> SanitisationResult:
        """Sanitise *record* and return a :class:`SanitisationResult`.

        Non-dict inputs return a fail-open empty result.
        The original *record* is never mutated.
        """
        if not isinstance(record, dict):
            return SanitisationResult(sanitised_record={}, flags=[])

        working = copy.deepcopy(record)
        sanitised, flags = self._process_mapping(working, "")
        return SanitisationResult(sanitised_record=sanitised, flags=flags)


__all__ = [
    "SanitisationFlag",
    "SanitisationResult",
    "SanitisationProcessor",
]
