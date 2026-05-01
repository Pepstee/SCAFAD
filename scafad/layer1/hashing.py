"""
layers/layer1/hashing.py
=========================

Deferred hashing manager for the L1 Behavioural Intake Zone.

WP-3.5 / DL-032
=================

``DeferredHashingManager`` replaces nominated field values with
cryptographic digests (SHA-256 or BLAKE2b).  A salt is applied using
cryptographically sound keyed constructions to prevent rainbow-table
and length-extension attacks:

- SHA-256: HMAC-SHA256(key=salt, msg=value)
- BLAKE2b: native keyed mode blake2b(data=value, key=salt[:64])

Salt resolution order
---------------------
1. ``salt`` constructor argument (highest priority).
2. ``SCAFAD_HASH_SALT`` environment variable.
3. Empty string (fallback — logs a warning at INFO level).

Key rule: anomaly-critical fields (from ``CRITICAL_FIELDS`` in
``preservation.py``) are never hashed.

Public API
----------
``HashingAction``          — Dataclass: field_path, algorithm
``HashingResult``          — Dataclass: hashed_record, actions
``DeferredHashingManager`` — .hash_fields(record, hash_fields, algorithm) → HashingResult
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .preservation import CRITICAL_FIELDS as _CRITICAL_FIELDS

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class HashingAction:
    """Records a single field-hashing event."""

    field_path: str   # dotted path, e.g. "function_name"
    algorithm: str    # "sha256" | "blake2b"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_path": self.field_path,
            "algorithm": self.algorithm,
        }


@dataclass
class HashingResult:
    """Output of a single hashing pass."""

    hashed_record: Dict[str, Any]
    actions: List[HashingAction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hashed_record": copy.deepcopy(self.hashed_record),
            "actions": [a.to_dict() for a in self.actions],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DEFAULT_ALGORITHM = "sha256"
_SUPPORTED_ALGORITHMS = {"sha256", "blake2b"}


def _resolve_salt(explicit: Optional[str]) -> str:
    if explicit is not None:
        return explicit
    env_salt = os.environ.get("SCAFAD_HASH_SALT")
    if env_salt:
        return env_salt
    _log.info(
        "SCAFAD_HASH_SALT not set and no explicit salt provided; "
        "using empty salt (insecure for production)."
    )
    return ""


def _digest(value: str, salt: str, algorithm: str) -> str:
    """Return the keyed digest of *value* under *salt* using *algorithm*.

    SHA-256:  HMAC-SHA256(key=salt, msg=value) — avoids length-extension
              attacks and is the standard keyed-hash construction for SHA-2.
    BLAKE2b:  BLAKE2b(data=value, key=salt[:64]) — uses BLAKE2b's native
              keyed mode (MAC), capped at 64 bytes as required by the spec.
              Falls back to unkeyed BLAKE2b when salt is empty.
    """
    data = value.encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    if algorithm == "sha256":
        return hmac.new(salt_bytes, data, hashlib.sha256).hexdigest()
    if algorithm == "blake2b":
        key = salt_bytes[:64]
        if key:
            return hashlib.blake2b(data, key=key).hexdigest()
        return hashlib.blake2b(data).hexdigest()
    alg_repr = repr(algorithm)
    raise ValueError(f"Unsupported hashing algorithm: {alg_repr}")


def _resolve_dotted(record: Dict[str, Any], path: str) -> Optional[Any]:
    """Return the value at *path* (dot-separated) in *record*, or None."""
    parts = path.split(".")
    node: Any = record
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _set_dotted(record: Dict[str, Any], path: str, value: Any) -> None:
    """Set the value at *path* (dot-separated) in *record*."""
    parts = path.split(".")
    node = record
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class DeferredHashingManager:
    """Hash nominated fields in an L1 record using SHA-256 or BLAKE2b.

    Usage::

        mgr = DeferredHashingManager(salt="my-secret")
        result = mgr.hash_fields(record, hash_fields=["function_name"])

    The manager operates on a deep copy of *record*; the original is never
    mutated.  Fields in ``CRITICAL_FIELDS`` are silently skipped even if
    nominated.  Non-dict inputs return a fail-open empty result.
    """

    def __init__(self, salt: Optional[str] = None) -> None:
        self._salt = _resolve_salt(salt)

    def hash_fields(
        self,
        record: Any,
        hash_fields: List[str],
        algorithm: str = _DEFAULT_ALGORITHM,
    ) -> HashingResult:
        """Hash *hash_fields* in *record* and return a :class:`HashingResult`.

        Parameters
        ----------
        record:
            The L1 record dict to process.
        hash_fields:
            Dotted field paths to hash.  Fields absent from *record* or in
            ``CRITICAL_FIELDS`` are silently skipped.
        algorithm:
            ``"sha256"`` (default) or ``"blake2b"``.
        """
        if not isinstance(record, dict):
            return HashingResult(hashed_record={}, actions=[])

        if algorithm not in _SUPPORTED_ALGORITHMS:
            raise ValueError(
                f"algorithm must be one of {sorted(_SUPPORTED_ALGORITHMS)}, "
                f"got {repr(algorithm)}"
            )

        working = copy.deepcopy(record)
        actions: List[HashingAction] = []

        for path in hash_fields:
            # Skip anomaly-critical fields
            if path in _CRITICAL_FIELDS:
                continue

            value = _resolve_dotted(working, path)
            if value is None:
                continue  # absent or non-string — skip silently

            str_value = str(value)
            digest = _digest(str_value, self._salt, algorithm)
            _set_dotted(working, path, digest)
            actions.append(HashingAction(field_path=path, algorithm=algorithm))

        return HashingResult(hashed_record=working, actions=actions)


__all__ = [
    "HashingAction",
    "HashingResult",
    "DeferredHashingManager",
]
