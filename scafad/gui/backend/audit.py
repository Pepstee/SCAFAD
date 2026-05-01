"""Audit dispatcher for SCAFAD GUI (Phase 4).

Every write route calls :func:`record_audit` exactly once after a successful
DB commit.  The function:

1. Serialises *payload* to canonical JSON (``sort_keys=True``, tight
   separators, ``ensure_ascii=False``).
2. Fetches the ``row_hash`` of the previous audit entry to build the
   SHA-256 hash chain (ADR-A4-4).
3. Computes a deterministic ``row_hash`` over the full row body.
4. Delegates persistence to ``store.append_audit_event()``.

Phase 4 audits only **writes**.  Read-event auditing is deferred to Phase 5
(sampled + Merkle-tree variant).  See ADR-A4-3.

ADR-A4-9: ``record_audit`` runs INSIDE the write route's existing transaction
boundary — if the write rolls back, the audit row rolls back with it.  In
practice this means callers should invoke ``record_audit`` AFTER their store
call has committed, and the audit row will be a separate but synchronous write.
The SQLite WAL mode ensures both rows are durable before the response is sent.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from fastapi import Request

from .store import AuditEventRow

logger = logging.getLogger("scafad.gui.audit")

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

VALID_SUBJECT_KINDS = frozenset({
    "detection", "case", "view", "inbox_bulk", "ingest", "system", "comment",
})

VALID_ACTIONS = frozenset({
    "created", "updated", "deleted", "attached", "detached",
    "exported", "viewed", "assigned", "dismissed",
})

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _canonical_json(obj: Any) -> str:
    """Serialise *obj* to canonical JSON (sort_keys, tight separators, unicode kept)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_row_hash(
    *,
    event_id: str,
    ts_str: str,
    actor_id: str,
    subject_kind: str,
    subject_id: Optional[str],
    action: str,
    payload_json: str,
    prev_hash: str,
) -> str:
    """Return SHA-256 hex digest over the canonical body of one audit row."""
    body = {
        "id": event_id,
        "ts": ts_str,
        "actor_id": actor_id,
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "action": action,
        "payload_json": payload_json,
        "prev_hash": prev_hash,
    }
    canonical = _canonical_json(body).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def record_audit(
    request: Request,
    *,
    actor_id: str,
    subject_kind: str,
    subject_id: Optional[str] = None,
    action: str,
    payload: Mapping[str, Any],
) -> AuditEventRow:
    """Append one row to the ``audit_events`` hash chain.

    Parameters
    ----------
    request:
        The current FastAPI request; used to reach ``app.state.store``.
    actor_id:
        Authenticated user id (from :func:`~.users.get_current_user`).
    subject_kind:
        Category of the target resource.  Must be one of
        ``'detection'``, ``'case'``, ``'view'``, ``'inbox_bulk'``,
        ``'ingest'``, ``'system'``, ``'comment'``.
    subject_id:
        Optional id of the target resource (``None`` for bulk actions and
        ingest events where a single id is not meaningful).
    action:
        Verb describing what happened.
    payload:
        Arbitrary metadata dict; will be canonicalised before storage.

    Returns
    -------
    AuditEventRow
        The newly persisted row.

    Raises
    ------
    ValueError
        When *subject_kind* is not in :data:`VALID_SUBJECT_KINDS`.
    """
    if subject_kind not in VALID_SUBJECT_KINDS:
        raise ValueError(
            f"Invalid subject_kind {subject_kind!r}; "
            f"must be one of {sorted(VALID_SUBJECT_KINDS)}"
        )

    store = request.app.state.store

    # Canonicalise the payload FIRST so it is part of the hash body.
    payload_json = _canonical_json(dict(payload))

    event_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc)
    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

    # Fetch the last row_hash to form the chain link.
    prev_hash: str = store.last_audit_row_hash() or ("0" * 64)

    row_hash = _compute_row_hash(
        event_id=event_id,
        ts_str=ts_str,
        actor_id=actor_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        action=action,
        payload_json=payload_json,
        prev_hash=prev_hash,
    )

    row = store.append_audit_event(
        actor_id=actor_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        action=action,
        payload_json=payload_json,
        prev_hash=prev_hash,
        row_hash=row_hash,
        event_id=event_id,
        ts=ts,
    )
    logger.debug(
        "audit row appended id=%s actor=%s kind=%s action=%s",
        event_id, actor_id, subject_kind, action,
    )
    return row


__all__ = ["record_audit", "VALID_SUBJECT_KINDS", "VALID_ACTIONS"]
