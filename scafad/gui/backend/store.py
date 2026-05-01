"""SQLite-backed persistence for SCAFAD GUI detections.

Phase 1 introduced the ``detections`` table — a single JSON-blob-plus-scalar
column row per persisted detection.

Phase 2 (this module) extends the schema with the case-management tables —
``cases``, ``case_detections``, ``comments``, ``case_events``, ``saved_views`` —
and the corresponding methods on :class:`DetectionStore`.  Every Phase-2 table
is created via ``CREATE TABLE IF NOT EXISTS`` so a cold start on a Phase-1 dev
DB is a no-op.

The :class:`DetectionStore` API stays compatible with Phase-1 callers: the
existing ``insert_detection``, ``get_detection``, ``list_detections``,
aggregate, and helper methods keep their signatures.  ``list_detections``
gains six OPTIONAL kwargs (``until``, ``mitre_technique``, ``decision``,
``risk_band``, ``text``, ``case_status``) which Phase-1 callers simply do not
pass.

ADRs honoured (see ``architecture_d64c2926-…``):

* **ADR-9** — cases are hard-deletable; ``case_events`` cascade is
  intentionally accepted (Phase 4 will surface orphan rows).
* **ADR-10** — ``cases.version`` is a monotonic int.  ``update_case`` raises
  :class:`VersionConflict` when ``expected_version`` does not match.
* **ADR-11** — bulk attach/detach is single-transaction with per-item results;
  the route layer composes the response.
* **ADR-14** — ``case_status`` filter LEFT JOINs through ``case_detections`` /
  ``cases``; no redundant column on ``detections``.
* **ADR-16** — ``saved_views`` carries ``owner_id`` so Phase 5 multi-user
  isolation lights up without schema change.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple


logger = logging.getLogger("scafad.gui.store")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA: List[str] = [
    # ---- Phase 1 ---------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS detections (
        id               TEXT PRIMARY KEY,
        ingested_at      TEXT NOT NULL,
        event_id         TEXT NOT NULL,
        function_id      TEXT NOT NULL,
        anomaly_type     TEXT NOT NULL,
        severity         TEXT NOT NULL,
        trust_score      REAL NOT NULL,
        mitre_techniques TEXT NOT NULL,
        decision         TEXT,
        risk_band        TEXT,
        duration_ms      REAL NOT NULL DEFAULT 0.0,
        correlation_id   TEXT,
        layer_payload    TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_detections_ingested ON detections(ingested_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_detections_severity  ON detections(severity)",
    "CREATE INDEX IF NOT EXISTS ix_detections_function  ON detections(function_id)",
    "CREATE INDEX IF NOT EXISTS ix_detections_type      ON detections(anomaly_type)",
    # ---- Phase 2 — cases -------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS cases (
        id              TEXT PRIMARY KEY,
        title           TEXT NOT NULL,
        status          TEXT NOT NULL CHECK (status IN ('open','triage','contained','closed')),
        severity_rollup TEXT NOT NULL,
        assignee_id     TEXT,
        opened_at       TEXT NOT NULL,
        closed_at       TEXT,
        created_by      TEXT NOT NULL,
        version         INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_cases_status   ON cases(status)",
    "CREATE INDEX IF NOT EXISTS ix_cases_assignee ON cases(assignee_id)",
    "CREATE INDEX IF NOT EXISTS ix_cases_opened   ON cases(opened_at DESC)",
    # ---- Phase 2 — case ↔ detection link --------------------------------
    """
    CREATE TABLE IF NOT EXISTS case_detections (
        case_id         TEXT NOT NULL,
        detection_id    TEXT NOT NULL UNIQUE,
        attached_at     TEXT NOT NULL,
        attached_by     TEXT NOT NULL,
        PRIMARY KEY (case_id, detection_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_cd_case      ON case_detections(case_id)",
    "CREATE INDEX IF NOT EXISTS ix_cd_detection ON case_detections(detection_id)",
    # ---- Phase 2 — comments ---------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS comments (
        id          TEXT PRIMARY KEY,
        case_id     TEXT NOT NULL,
        author_id   TEXT NOT NULL,
        body_md     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_comments_case ON comments(case_id, created_at)",
    # ---- Phase 2 — case_events ------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS case_events (
        id           TEXT PRIMARY KEY,
        case_id      TEXT NOT NULL,
        kind         TEXT NOT NULL CHECK (kind IN (
            'created','state_changed','assigned',
            'commented','detection_attached','detection_detached',
            'dismissed','reopened'
        )),
        payload_json TEXT NOT NULL,
        actor_id     TEXT NOT NULL,
        created_at   TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_case_events_case ON case_events(case_id, created_at)",
    # ---- Phase 2 — saved_views ------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS saved_views (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        owner_id    TEXT NOT NULL,
        filter_json TEXT NOT NULL,
        sort_json   TEXT NOT NULL DEFAULT '[]',
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL,
        pinned      INTEGER NOT NULL DEFAULT 0,
        UNIQUE (owner_id, name)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_views_owner ON saved_views(owner_id, pinned DESC)",
    # ---- Phase 3 — function rollups -----------------------------------
    "CREATE INDEX IF NOT EXISTS ix_detections_func_ingested ON detections(function_id, ingested_at DESC)",
    # ---- Phase 4 — audit log -----------------------------------------
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        id            TEXT PRIMARY KEY,
        ts            TEXT NOT NULL,
        actor_id      TEXT NOT NULL,
        subject_kind  TEXT NOT NULL CHECK (subject_kind IN (
            'detection','case','view','inbox_bulk','ingest','system','comment'
        )),
        subject_id    TEXT,
        action        TEXT NOT NULL,
        payload_json  TEXT NOT NULL,
        prev_hash     TEXT NOT NULL,
        row_hash      TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_events(ts DESC)",
    "CREATE INDEX IF NOT EXISTS ix_audit_subject ON audit_events(subject_kind, subject_id)",
    "CREATE INDEX IF NOT EXISTS ix_audit_actor ON audit_events(actor_id)",
]


# ---------------------------------------------------------------------------
# Row dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DetectionRow:
    """In-memory representation of a stored detection (DB-shaped)."""

    id: str
    ingested_at: datetime
    event_id: str
    function_id: str
    anomaly_type: str
    severity: str
    trust_score: float
    mitre_techniques: List[str] = field(default_factory=list)
    decision: Optional[str] = None
    risk_band: Optional[str] = None
    duration_ms: float = 0.0
    correlation_id: Optional[str] = None
    layer_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseRow:
    """In-memory representation of a case row."""

    id: str
    title: str
    status: str
    severity_rollup: str
    assignee_id: Optional[str]
    opened_at: datetime
    closed_at: Optional[datetime]
    created_by: str
    version: int
    detection_count: int = 0


@dataclass
class CommentRow:
    id: str
    case_id: str
    author_id: str
    body_md: str
    created_at: datetime


@dataclass
class CaseEventRow:
    id: str
    case_id: str
    kind: str
    payload: Dict[str, Any]
    actor_id: str
    created_at: datetime


@dataclass
class SavedViewRow:
    id: str
    name: str
    owner_id: str
    filter_json: Dict[str, Any]
    sort_json: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    pinned: bool


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 row dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FunctionRollupRow:
    """One row per distinct function_id in the detection stream."""

    function_id: str
    last_seen: datetime
    count_24h: int
    count_7d: int
    severity_max: str  # "observe", "review", "escalate"
    open_case_count: int
    top_mitre_techniques: List[str] = field(default_factory=list)


@dataclass
class FunctionDetailRows:
    """Multi-part aggregation for a single function in a time window."""

    severity_counts: Dict[str, int]  # severity → count
    mitre_counts: Dict[str, int]  # technique_id → count
    sparkline_bins: List[Dict[str, Any]]  # continuous bins, no gaps
    recent_detections: List[DetectionRow]  # newest-first, limit 20
    linked_cases: List[CaseRow]  # open cases


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 row dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AuditEventRow:
    """In-memory representation of one audit-trail entry (Phase 4)."""

    id: str
    ts: datetime
    actor_id: str
    subject_kind: str
    subject_id: Optional[str]
    action: str
    payload: Dict[str, Any]
    prev_hash: str
    row_hash: str


@dataclass
class ChainVerification:
    """Result of :meth:`DetectionStore.verify_audit_chain`."""

    ok: bool
    last_verified_id: Optional[str] = None
    broken_at: Optional[str] = None
    total_rows: int = 0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class StoreError(Exception):
    """Base class for typed errors raised by :class:`DetectionStore`."""


class NotFound(StoreError):
    """Requested entity does not exist."""


class VersionConflict(StoreError):
    """Optimistic-concurrency mismatch on a case mutation."""

    def __init__(self, *, current_version: int, expected_version: int) -> None:
        super().__init__(
            f"version conflict: current={current_version}, expected={expected_version}"
        )
        self.current_version = current_version
        self.expected_version = expected_version


class DuplicateAttachment(StoreError):
    """Tried to attach a detection that is already attached (to the same case)."""


class AlreadyAttached(StoreError):
    """Tried to attach a detection that is already attached to another case."""

    def __init__(self, *, detection_id: str, existing_case_id: str) -> None:
        super().__init__(
            f"detection '{detection_id}' is already attached to case "
            f"'{existing_case_id}'"
        )
        self.detection_id = detection_id
        self.existing_case_id = existing_case_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_VALID_STATES = {"open", "triage", "contained", "closed"}
_SEVERITY_ORDER = {"observe": 0, "review": 1, "escalate": 2}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_precise(value: datetime) -> str:
    """Sub-second-precision ISO-8601 stamp (used for case_events ordering)."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    utc = value.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond:06d}Z"


def _parse_iso(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw)


def _new_id() -> str:
    """Return a sortable, URL-safe identifier."""

    return uuid.uuid4().hex


def _max_severity(values: Iterable[str]) -> str:
    """Pick the highest-severity value from ``values`` (default ``observe``)."""

    best = "observe"
    best_rank = -1
    for v in values:
        rank = _SEVERITY_ORDER.get(str(v).lower(), -1)
        if rank > best_rank:
            best = str(v).lower()
            best_rank = rank
    return best if best_rank >= 0 else "observe"


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class DetectionStore:
    """Threadsafe wrapper around a single SQLite database file."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection / schema
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(
            str(self.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
            timeout=10.0,
        )
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            for stmt in _SCHEMA:
                conn.execute(stmt)
            conn.commit()

    # ------------------------------------------------------------------
    # Detections — insert / read (Phase 1, unchanged signatures)
    # ------------------------------------------------------------------

    def insert_detection(
        self,
        *,
        event_id: str,
        function_id: str,
        anomaly_type: str,
        severity: str,
        trust_score: float,
        mitre_techniques: Sequence[str],
        layer_payload: Dict[str, Any],
        decision: Optional[str] = None,
        risk_band: Optional[str] = None,
        duration_ms: float = 0.0,
        correlation_id: Optional[str] = None,
        ingested_at: Optional[datetime] = None,
        detection_id: Optional[str] = None,
    ) -> DetectionRow:
        """Persist a detection and return its stored row."""

        row_id = detection_id or _new_id()
        ts = ingested_at or _utc_now()
        techniques_json = json.dumps(list(mitre_techniques))
        payload_json = json.dumps(layer_payload, default=str)

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO detections (
                    id, ingested_at, event_id, function_id, anomaly_type,
                    severity, trust_score, mitre_techniques, decision,
                    risk_band, duration_ms, correlation_id, layer_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    _iso(ts),
                    event_id,
                    function_id,
                    anomaly_type,
                    severity,
                    float(trust_score),
                    techniques_json,
                    decision,
                    risk_band,
                    float(duration_ms),
                    correlation_id,
                    payload_json,
                ),
            )
            conn.commit()

        return DetectionRow(
            id=row_id,
            ingested_at=ts,
            event_id=event_id,
            function_id=function_id,
            anomaly_type=anomaly_type,
            severity=severity,
            trust_score=float(trust_score),
            mitre_techniques=list(mitre_techniques),
            decision=decision,
            risk_band=risk_band,
            duration_ms=float(duration_ms),
            correlation_id=correlation_id,
            layer_payload=layer_payload,
        )

    def get_detection(self, detection_id: str) -> Optional[DetectionRow]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM detections WHERE id = ?", (detection_id,)
            ).fetchone()
        return self._row_to_obj(row) if row else None

    def list_detections(
        self,
        *,
        severity: Optional[str] = None,
        anomaly_type: Optional[str] = None,
        function_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        mitre_technique: Optional[str] = None,
        decision: Optional[str] = None,
        risk_band: Optional[str] = None,
        text: Optional[str] = None,
        case_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[DetectionRow], int]:
        """Return ``(items, total)`` filtered by the supplied parameters.

        All Phase-1 kwargs (``severity``, ``anomaly_type``, ``function_id``,
        ``since``, ``limit``, ``offset``) keep their original meaning.

        Phase 2 adds:

        * ``until`` — exclusive upper bound on ``ingested_at``
        * ``mitre_technique`` — substring match on the JSON techniques column
        * ``decision`` / ``risk_band`` — exact match
        * ``text`` — case-insensitive substring across
          ``event_id``/``function_id``/``correlation_id``
        * ``case_status`` — joins through ``case_detections`` and ``cases``;
          the special value ``"none"`` matches detections without any case
          link.
        """

        where: List[str] = []
        params: List[Any] = []

        # ── Phase-1 filters ────────────────────────────────────────────
        if severity:
            where.append("d.severity = ?")
            params.append(severity)
        if anomaly_type:
            where.append("d.anomaly_type = ?")
            params.append(anomaly_type)
        if function_id:
            where.append("d.function_id = ?")
            params.append(function_id)
        if since is not None:
            where.append("d.ingested_at >= ?")
            params.append(_iso(since))

        # ── Phase-2 filters ────────────────────────────────────────────
        if until is not None:
            where.append("d.ingested_at < ?")
            params.append(_iso(until))
        if mitre_technique:
            # Match either ``"T1059"`` or ``"T1059.001"`` substrings inside
            # the JSON-encoded techniques column.
            where.append("d.mitre_techniques LIKE ?")
            params.append(f'%"{mitre_technique}%')
        if decision:
            where.append("d.decision = ?")
            params.append(decision)
        if risk_band:
            where.append("d.risk_band = ?")
            params.append(risk_band)
        if text:
            where.append(
                "(LOWER(d.event_id) LIKE ? OR LOWER(d.function_id) LIKE ? "
                "OR LOWER(IFNULL(d.correlation_id, '')) LIKE ?)"
            )
            needle = f"%{text.lower()}%"
            params.extend([needle, needle, needle])

        # ── case_status filter (LEFT JOIN per ADR-14) ─────────────────
        join_clause = ""
        select_extra = ""
        case_filter_clause: Optional[str] = None
        if case_status is not None:
            join_clause = (
                " LEFT JOIN case_detections cd ON cd.detection_id = d.id "
                " LEFT JOIN cases c            ON c.id            = cd.case_id "
            )
            select_extra = ", c.id AS case_id, c.status AS case_status_v"
            if case_status == "none":
                case_filter_clause = "(cd.case_id IS NULL)"
            else:
                case_filter_clause = "(c.status = ?)"
                params.append(case_status)
        if case_filter_clause:
            where.append(case_filter_clause)

        clause = ("WHERE " + " AND ".join(where)) if where else ""

        with self._lock, self._connect() as conn:
            total_q = (
                f"SELECT COUNT(DISTINCT d.id) FROM detections d {join_clause} {clause}"
            )
            total = conn.execute(total_q, tuple(params)).fetchone()[0]
            rows_q = (
                f"SELECT DISTINCT d.*{select_extra} "
                f"FROM detections d {join_clause} {clause} "
                f"ORDER BY d.ingested_at DESC LIMIT ? OFFSET ?"
            )
            rows = conn.execute(
                rows_q, tuple(params) + (int(limit), int(offset))
            ).fetchall()
        return [self._row_to_obj(r) for r in rows], int(total)

    # ------------------------------------------------------------------
    # Aggregates (Phase 1, unchanged)
    # ------------------------------------------------------------------

    def total_count(self) -> int:
        with self._lock, self._connect() as conn:
            return int(
                conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
            )

    def severity_mix(self) -> Dict[str, int]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT severity, COUNT(*) AS n FROM detections GROUP BY severity"
            ).fetchall()
        out: Dict[str, int] = {"observe": 0, "review": 0, "escalate": 0}
        for row in rows:
            sev = (row["severity"] or "observe").lower()
            if sev in out:
                out[sev] = int(row["n"])
        return out

    def ingest_rate_last_hour(self) -> int:
        cutoff = _utc_now() - timedelta(hours=1)
        with self._lock, self._connect() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM detections WHERE ingested_at >= ?",
                    (_iso(cutoff),),
                ).fetchone()[0]
            )

    def histogram_24h(self) -> List[Dict[str, Any]]:
        now = _utc_now().replace(minute=0, second=0, microsecond=0)
        buckets: List[Dict[str, Any]] = []
        with self._lock, self._connect() as conn:
            for offset_h in range(23, -1, -1):
                start = now - timedelta(hours=offset_h)
                end = start + timedelta(hours=1)
                rows = conn.execute(
                    """
                    SELECT severity, COUNT(*) AS n FROM detections
                    WHERE ingested_at >= ? AND ingested_at < ?
                    GROUP BY severity
                    """,
                    (_iso(start), _iso(end)),
                ).fetchall()
                bucket = {"hour": _iso(start), "observe": 0, "review": 0, "escalate": 0}
                for r in rows:
                    sev = (r["severity"] or "").lower()
                    if sev in bucket:
                        bucket[sev] = int(r["n"])
                buckets.append(bucket)
        return buckets

    def last_ingest_at(self) -> Optional[datetime]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(ingested_at) AS m FROM detections"
            ).fetchone()
        return _parse_iso(row["m"]) if row and row["m"] else None

    def db_size_bytes(self) -> int:
        try:
            return int(self.db_path.stat().st_size)
        except OSError:
            return 0

    # ------------------------------------------------------------------
    # Bulk helpers (Phase 1)
    # ------------------------------------------------------------------

    def truncate(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM detections")
            conn.execute("DELETE FROM case_detections")
            conn.execute("DELETE FROM comments")
            conn.execute("DELETE FROM case_events")
            conn.execute("DELETE FROM cases")
            conn.commit()

    # ------------------------------------------------------------------
    # Phase-2: Cases
    # ------------------------------------------------------------------

    def create_case(
        self,
        *,
        title: str,
        created_by: str,
        detection_ids: Sequence[str] = (),
        assignee_id: Optional[str] = None,
        status: str = "open",
        opened_at: Optional[datetime] = None,
    ) -> CaseRow:
        """Create a new case and optionally attach an initial set of detections.

        Re-attaching a detection that already belongs to another case raises
        :class:`AlreadyAttached`.  The case is committed atomically with its
        attachments.
        """

        if status not in _VALID_STATES:
            raise StoreError(f"invalid status '{status}'")

        case_id = _new_id()
        ts = opened_at or _utc_now()
        actor = created_by

        # Compute the severity rollup from the attached detections (if any).
        rollup = "observe"
        with self._lock, self._connect() as conn:
            if detection_ids:
                placeholders = ",".join("?" for _ in detection_ids)
                severities = [
                    str(r["severity"]) for r in conn.execute(
                        f"SELECT severity FROM detections WHERE id IN ({placeholders})",
                        tuple(detection_ids),
                    ).fetchall()
                ]
                rollup = _max_severity(severities) if severities else "observe"
                # Reject if any are already attached.
                existing = {
                    r["detection_id"]: r["case_id"]
                    for r in conn.execute(
                        f"SELECT detection_id, case_id FROM case_detections "
                        f"WHERE detection_id IN ({placeholders})",
                        tuple(detection_ids),
                    ).fetchall()
                }
                conflict = next(iter(existing.items()), None)
                if conflict:
                    raise AlreadyAttached(
                        detection_id=conflict[0], existing_case_id=conflict[1]
                    )

            conn.execute(
                """
                INSERT INTO cases (
                    id, title, status, severity_rollup, assignee_id,
                    opened_at, closed_at, created_by, version
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, 1)
                """,
                (
                    case_id,
                    title.strip() or "Untitled case",
                    status,
                    rollup,
                    assignee_id,
                    _iso(ts),
                    created_by,
                ),
            )
            for did in detection_ids:
                conn.execute(
                    """
                    INSERT INTO case_detections
                        (case_id, detection_id, attached_at, attached_by)
                    VALUES (?, ?, ?, ?)
                    """,
                    (case_id, did, _iso(ts), actor),
                )
            self._record_event(
                conn,
                case_id=case_id,
                kind="created",
                payload={
                    "title": title,
                    "status": status,
                    "assignee_id": assignee_id,
                    "detection_count": len(list(detection_ids)),
                },
                actor_id=actor,
            )
            conn.commit()

        return self._fetch_case(case_id)

    def get_case(self, case_id: str) -> Optional[CaseRow]:
        try:
            return self._fetch_case(case_id)
        except NotFound:
            return None

    def list_cases(
        self,
        *,
        status: Optional[str] = None,
        assignee_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[CaseRow], int]:
        where: List[str] = []
        params: List[Any] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if assignee_id is not None:
            if assignee_id == "":
                where.append("assignee_id IS NULL")
            else:
                where.append("assignee_id = ?")
                params.append(assignee_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        with self._lock, self._connect() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM cases {clause}", tuple(params)
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT c.*,
                       (SELECT COUNT(*) FROM case_detections cd
                        WHERE cd.case_id = c.id) AS detection_count
                FROM cases c
                {clause}
                ORDER BY c.opened_at DESC
                LIMIT ? OFFSET ?
                """,
                tuple(params) + (int(limit), int(offset)),
            ).fetchall()
        return [self._row_to_case(r) for r in rows], int(total)

    def update_case(
        self,
        case_id: str,
        *,
        expected_version: int,
        actor_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
        assignee_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> CaseRow:
        """Optimistic-concurrency case mutation.

        Raises :class:`VersionConflict` if ``expected_version`` no longer
        matches the row's current ``version``.  Each mutation produces one or
        more ``case_events`` rows.
        """

        if status is not None and status not in _VALID_STATES:
            raise StoreError(f"invalid status '{status}'")

        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
            if row is None:
                raise NotFound(f"case '{case_id}' not found")
            current_version = int(row["version"])
            if current_version != int(expected_version):
                raise VersionConflict(
                    current_version=current_version,
                    expected_version=int(expected_version),
                )

            sets: List[str] = []
            params: List[Any] = []
            events: List[Tuple[str, Dict[str, Any]]] = []

            if title is not None and title != row["title"]:
                sets.append("title = ?")
                params.append(title)

            old_status = row["status"]
            if status is not None and status != old_status:
                sets.append("status = ?")
                params.append(status)
                if status == "closed":
                    sets.append("closed_at = ?")
                    params.append(_iso(_utc_now()))
                if old_status == "closed" and status != "closed":
                    sets.append("closed_at = NULL")
                kind = "reopened" if old_status == "closed" else "state_changed"
                events.append(
                    (
                        kind,
                        {"from": old_status, "to": status, "reason": reason},
                    )
                )

            old_assignee = row["assignee_id"]
            if assignee_id is not None and assignee_id != old_assignee:
                sets.append("assignee_id = ?")
                # Empty string is a request to UNASSIGN.
                params.append(assignee_id or None)
                events.append(
                    (
                        "assigned",
                        {"from": old_assignee, "to": assignee_id or None},
                    )
                )

            sets.append("version = version + 1")

            if sets:
                conn.execute(
                    f"UPDATE cases SET {', '.join(sets)} WHERE id = ?",
                    tuple(params) + (case_id,),
                )

            for kind, payload in events:
                self._record_event(
                    conn,
                    case_id=case_id,
                    kind=kind,
                    payload=payload,
                    actor_id=actor_id,
                )

            conn.commit()

        return self._fetch_case(case_id)

    def delete_case(self, case_id: str, *, actor_id: str) -> None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
            if row is None:
                raise NotFound(f"case '{case_id}' not found")
            # Cascade-equivalent (SQLite FKs are off by default in our config).
            conn.execute("DELETE FROM case_detections WHERE case_id = ?", (case_id,))
            conn.execute("DELETE FROM comments WHERE case_id = ?", (case_id,))
            conn.execute("DELETE FROM case_events WHERE case_id = ?", (case_id,))
            conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
            conn.commit()

    # ------------------------------------------------------------------
    # Phase-2: Attachments
    # ------------------------------------------------------------------

    def attach_detection(
        self,
        case_id: str,
        detection_id: str,
        *,
        actor_id: str,
    ) -> None:
        with self._lock, self._connect() as conn:
            case = conn.execute(
                "SELECT id FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
            if case is None:
                raise NotFound(f"case '{case_id}' not found")
            existing = conn.execute(
                "SELECT case_id FROM case_detections WHERE detection_id = ?",
                (detection_id,),
            ).fetchone()
            if existing is not None:
                if existing["case_id"] == case_id:
                    raise DuplicateAttachment(
                        f"detection '{detection_id}' already attached"
                    )
                raise AlreadyAttached(
                    detection_id=detection_id, existing_case_id=existing["case_id"]
                )
            conn.execute(
                """
                INSERT INTO case_detections (case_id, detection_id, attached_at, attached_by)
                VALUES (?, ?, ?, ?)
                """,
                (case_id, detection_id, _iso(_utc_now()), actor_id),
            )
            self._record_event(
                conn,
                case_id=case_id,
                kind="detection_attached",
                payload={"detection_id": detection_id},
                actor_id=actor_id,
            )
            self._refresh_severity_rollup(conn, case_id)
            conn.commit()

    def detach_detection(
        self,
        case_id: str,
        detection_id: str,
        *,
        actor_id: str,
    ) -> None:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM case_detections
                WHERE case_id = ? AND detection_id = ?
                """,
                (case_id, detection_id),
            )
            if cursor.rowcount == 0:
                raise NotFound(
                    f"detection '{detection_id}' is not attached to case '{case_id}'"
                )
            self._record_event(
                conn,
                case_id=case_id,
                kind="detection_detached",
                payload={"detection_id": detection_id},
                actor_id=actor_id,
            )
            self._refresh_severity_rollup(conn, case_id)
            conn.commit()

    def case_for_detection(self, detection_id: str) -> Optional[CaseRow]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT c.*,
                       (SELECT COUNT(*) FROM case_detections cd2
                        WHERE cd2.case_id = c.id) AS detection_count
                FROM case_detections cd
                JOIN cases c ON c.id = cd.case_id
                WHERE cd.detection_id = ?
                """,
                (detection_id,),
            ).fetchone()
        return self._row_to_case(row) if row else None

    def list_case_detections(self, case_id: str) -> List[DetectionRow]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT d.* FROM case_detections cd
                JOIN detections d ON d.id = cd.detection_id
                WHERE cd.case_id = ?
                ORDER BY d.ingested_at DESC
                """,
                (case_id,),
            ).fetchall()
        return [self._row_to_obj(r) for r in rows]

    # ------------------------------------------------------------------
    # Phase-2: Comments
    # ------------------------------------------------------------------

    def add_comment(
        self,
        case_id: str,
        author_id: str,
        body_md: str,
    ) -> CommentRow:
        body = (body_md or "").strip()
        if not body:
            raise StoreError("comment body must not be empty")
        with self._lock, self._connect() as conn:
            case = conn.execute(
                "SELECT id FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
            if case is None:
                raise NotFound(f"case '{case_id}' not found")
            comment_id = _new_id()
            now = _iso(_utc_now())
            conn.execute(
                """
                INSERT INTO comments (id, case_id, author_id, body_md, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (comment_id, case_id, author_id, body, now),
            )
            self._record_event(
                conn,
                case_id=case_id,
                kind="commented",
                payload={"comment_id": comment_id, "preview": body[:120]},
                actor_id=author_id,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM comments WHERE id = ?", (comment_id,)
            ).fetchone()
        return self._row_to_comment(row)

    def list_comments(self, case_id: str) -> List[CommentRow]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM comments WHERE case_id = ?
                ORDER BY created_at ASC
                """,
                (case_id,),
            ).fetchall()
        return [self._row_to_comment(r) for r in rows]

    # ------------------------------------------------------------------
    # Phase-2: Case events
    # ------------------------------------------------------------------

    def record_case_event(
        self,
        case_id: str,
        kind: str,
        payload: Mapping[str, Any],
        actor_id: str,
    ) -> CaseEventRow:
        with self._lock, self._connect() as conn:
            event_id = self._record_event(
                conn,
                case_id=case_id,
                kind=kind,
                payload=dict(payload),
                actor_id=actor_id,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM case_events WHERE id = ?", (event_id,)
            ).fetchone()
        return self._row_to_event(row)

    def list_case_events(self, case_id: str) -> List[CaseEventRow]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM case_events WHERE case_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (case_id,),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    # ------------------------------------------------------------------
    # Phase-2: Saved views
    # ------------------------------------------------------------------

    def create_view(
        self,
        *,
        owner_id: str,
        name: str,
        filter_json: Mapping[str, Any],
        sort_json: Sequence[Mapping[str, Any]] = (),
        pinned: bool = False,
    ) -> SavedViewRow:
        if not (name and name.strip()):
            raise StoreError("view name must not be empty")
        view_id = _new_id()
        now = _iso(_utc_now())
        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO saved_views
                        (id, name, owner_id, filter_json, sort_json,
                         created_at, updated_at, pinned)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        view_id,
                        name.strip(),
                        owner_id,
                        json.dumps(dict(filter_json)),
                        json.dumps([dict(x) for x in sort_json]),
                        now,
                        now,
                        1 if pinned else 0,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise StoreError(
                    f"saved view '{name}' already exists for owner"
                ) from exc
            row = conn.execute(
                "SELECT * FROM saved_views WHERE id = ?", (view_id,)
            ).fetchone()
        return self._row_to_view(row)

    def update_view(
        self,
        view_id: str,
        *,
        owner_id: str,
        name: Optional[str] = None,
        filter_json: Optional[Mapping[str, Any]] = None,
        sort_json: Optional[Sequence[Mapping[str, Any]]] = None,
        pinned: Optional[bool] = None,
    ) -> SavedViewRow:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM saved_views WHERE id = ? AND owner_id = ?",
                (view_id, owner_id),
            ).fetchone()
            if row is None:
                raise NotFound(f"view '{view_id}' not found")
            sets: List[str] = []
            params: List[Any] = []
            if name is not None:
                sets.append("name = ?")
                params.append(name.strip())
            if filter_json is not None:
                sets.append("filter_json = ?")
                params.append(json.dumps(dict(filter_json)))
            if sort_json is not None:
                sets.append("sort_json = ?")
                params.append(json.dumps([dict(x) for x in sort_json]))
            if pinned is not None:
                sets.append("pinned = ?")
                params.append(1 if pinned else 0)
            sets.append("updated_at = ?")
            params.append(_iso(_utc_now()))
            try:
                conn.execute(
                    f"UPDATE saved_views SET {', '.join(sets)} "
                    f"WHERE id = ? AND owner_id = ?",
                    tuple(params) + (view_id, owner_id),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise StoreError("view name collides with an existing view") from exc
            row = conn.execute(
                "SELECT * FROM saved_views WHERE id = ?", (view_id,)
            ).fetchone()
        return self._row_to_view(row)

    def delete_view(self, view_id: str, *, owner_id: str) -> None:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM saved_views WHERE id = ? AND owner_id = ?",
                (view_id, owner_id),
            )
            if cursor.rowcount == 0:
                raise NotFound(f"view '{view_id}' not found")
            conn.commit()

    def list_views(self, owner_id: str) -> List[SavedViewRow]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM saved_views WHERE owner_id = ?
                ORDER BY pinned DESC, name ASC
                """,
                (owner_id,),
            ).fetchall()
        return [self._row_to_view(r) for r in rows]

    def get_view(self, view_id: str, owner_id: str) -> Optional[SavedViewRow]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM saved_views WHERE id = ? AND owner_id = ?",
                (view_id, owner_id),
            ).fetchone()
        return self._row_to_view(row) if row else None

    # ------------------------------------------------------------------
    # Phase 3: Function-level aggregates
    # ------------------------------------------------------------------

    def function_rollup(
        self,
        *,
        severity: Optional[str] = None,
        mitre_technique: Optional[str] = None,
        sort: str = "last_seen_desc",
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Aggregate one row per distinct function_id.

        Args:
            severity: Optional severity filter.
            mitre_technique: Optional MITRE technique substring.
            sort: One of last_seen_desc, count_24h_desc, count_7d_desc, open_case_count_desc.
            limit: Result limit.
            offset: Result offset.

        Returns:
            Tuple of (rows, total_count_of_distinct_functions).
        """
        now = _utc_now()
        cutoff_24h = _iso(now - timedelta(hours=24))
        cutoff_7d = _iso(now - timedelta(days=7))

        # Build where clause
        where: List[str] = ["1"]
        params: List[Any] = []
        if severity:
            where.append("d.severity = ?")
            params.append(severity)
        if mitre_technique:
            where.append("d.mitre_techniques LIKE ?")
            params.append(f'%"{mitre_technique}%')

        where_clause = " AND ".join(where)

        # Map sort to ORDER BY clause
        sort_order = "MAX(d.ingested_at) DESC"
        if sort == "count_24h_desc":
            sort_order = "count_24h DESC, MAX(d.ingested_at) DESC"
        elif sort == "count_7d_desc":
            sort_order = "count_7d DESC, MAX(d.ingested_at) DESC"
        elif sort == "open_case_count_desc":
            sort_order = "COALESCE(open_case_count, 0) DESC, MAX(d.ingested_at) DESC"

        with self._lock, self._connect() as conn:
            # Get total count of distinct functions matching filters
            total_q = f"""
                SELECT COUNT(DISTINCT d.function_id)
                FROM detections d
                WHERE {where_clause}
            """
            total = conn.execute(total_q, tuple(params)).fetchone()[0]

            # Get paginated list of functions with aggregates
            rows_q = f"""
                SELECT
                    d.function_id,
                    MAX(d.ingested_at) AS last_seen,
                    SUM(CASE WHEN d.ingested_at >= ? THEN 1 ELSE 0 END) AS count_24h,
                    SUM(CASE WHEN d.ingested_at >= ? THEN 1 ELSE 0 END) AS count_7d,
                    (SELECT MAX(severity) FROM (
                        SELECT severity, CASE
                            WHEN severity = 'escalate' THEN 3
                            WHEN severity = 'review' THEN 2
                            WHEN severity = 'observe' THEN 1
                            ELSE 0
                        END AS sev_order
                        FROM detections
                        WHERE function_id = d.function_id AND {where_clause}
                        ORDER BY sev_order DESC
                        LIMIT 1
                    )) AS severity_max,
                    COALESCE((
                        SELECT COUNT(DISTINCT c.id)
                        FROM case_detections cd
                        LEFT JOIN cases c ON c.id = cd.case_id
                        WHERE cd.detection_id IN (
                            SELECT id FROM detections
                            WHERE function_id = d.function_id
                        )
                        AND c.status != 'closed'
                    ), 0) AS open_case_count,
                    GROUP_CONCAT(DISTINCT json_extract(t.value, '$'), ',')
                        AS top_mitre_techniques
                FROM detections d
                LEFT JOIN json_each(d.mitre_techniques) t ON 1=1
                WHERE {where_clause}
                GROUP BY d.function_id
                ORDER BY {sort_order}
                LIMIT ? OFFSET ?
            """
            params_full = tuple(params) + (cutoff_24h, cutoff_7d) + tuple(params) * 0
            rows = conn.execute(
                rows_q,
                (cutoff_24h, cutoff_7d) + tuple(params) + (int(limit), int(offset))
            ).fetchall()

        return [dict(r) for r in rows], int(total)

    def function_detail_rows(
        self,
        function_id: str,
        *,
        since: datetime,
        until: datetime,
    ) -> FunctionDetailRows:
        """Fetch aggregates for a single function in a time window.

        Returns:
            FunctionDetailRows with severity_counts, mitre_counts, sparkline_bins,
            recent_detections (newest-first, limit 20), and linked_cases.
        """
        since_iso = _iso(since)
        until_iso = _iso(until)

        with self._lock, self._connect() as conn:
            # Severity distribution
            severity_rows = conn.execute(
                """
                SELECT severity, COUNT(*) AS cnt
                FROM detections
                WHERE function_id = ? AND ingested_at >= ? AND ingested_at < ?
                GROUP BY severity
                """,
                (function_id, since_iso, until_iso),
            ).fetchall()
            severity_counts = {row["severity"]: row["cnt"] for row in severity_rows}

            # MITRE technique distribution
            mitre_rows = conn.execute(
                """
                SELECT json_extract(t.value, '$') AS technique, COUNT(*) AS cnt
                FROM detections d, json_each(d.mitre_techniques) t
                WHERE d.function_id = ? AND d.ingested_at >= ? AND d.ingested_at < ?
                GROUP BY technique
                """,
                (function_id, since_iso, until_iso),
            ).fetchall()
            mitre_counts = {row["technique"]: row["cnt"] for row in mitre_rows}

            # Recent detections (newest-first, limit 20)
            recent_rows = conn.execute(
                """
                SELECT *
                FROM detections
                WHERE function_id = ? AND ingested_at >= ? AND ingested_at < ?
                ORDER BY ingested_at DESC
                LIMIT 20
                """,
                (function_id, since_iso, until_iso),
            ).fetchall()
            recent_detections = [self._row_to_obj(r) for r in recent_rows]

            # Linked open cases
            case_rows = conn.execute(
                """
                SELECT DISTINCT c.*,
                       (SELECT COUNT(*) FROM case_detections cd
                        WHERE cd.case_id = c.id) AS detection_count
                FROM cases c
                LEFT JOIN case_detections cd ON cd.case_id = c.id
                WHERE cd.detection_id IN (
                    SELECT id FROM detections
                    WHERE function_id = ?
                )
                AND c.status != 'closed'
                ORDER BY c.opened_at DESC
                """,
                (function_id,),
            ).fetchall()
            linked_cases = [self._row_to_case(r) for r in case_rows]

        return FunctionDetailRows(
            severity_counts=severity_counts,
            mitre_counts=mitre_counts,
            sparkline_bins=[],  # Filled by histogram_for_function
            recent_detections=recent_detections,
            linked_cases=linked_cases,
        )

    def histogram_for_function(
        self,
        function_id: str,
        *,
        since: datetime,
        until: datetime,
        bin: str,
    ) -> List[Dict[str, Any]]:
        """Return a continuous bin sequence (no gaps) for a function.

        Args:
            function_id: The function ID.
            since: Inclusive lower bound.
            until: Exclusive upper bound.
            bin: One of "1h", "6h", "1d", "3d".

        Returns:
            List of dicts: {bucket_start, count, severity_max}
        """
        since_iso = _iso(since)
        until_iso = _iso(until)

        # Determine bin size
        bin_seconds = {
            "1h": 60 * 60,
            "6h": 6 * 60 * 60,
            "1d": 24 * 60 * 60,
            "3d": 3 * 24 * 60 * 60,
        }.get(bin, 24 * 60 * 60)

        with self._lock, self._connect() as conn:
            # Get observed data
            rows = conn.execute(
                """
                SELECT
                    datetime((strftime('%s', ingested_at) / ?) * ?,
                             'unixepoch') AS bucket_start,
                    COUNT(*) AS count,
                    MAX(CASE
                        WHEN severity = 'escalate' THEN 'escalate'
                        WHEN severity = 'review' THEN 'review'
                        ELSE 'observe'
                    END) AS severity_max
                FROM detections
                WHERE function_id = ? AND ingested_at >= ? AND ingested_at < ?
                GROUP BY bucket_start
                ORDER BY bucket_start ASC
                """,
                (bin_seconds, bin_seconds, function_id, since_iso, until_iso),
            ).fetchall()

        observed = {row["bucket_start"]: row for row in rows}

        # Generate complete sequence
        result = []
        current = since
        while current < until:
            bucket_start = _iso(current)
            result.append({
                "bucket_start": bucket_start,
                "count": observed.get(bucket_start, {}).get("count", 0),
                "severity_max": observed.get(bucket_start, {}).get("severity_max"),
            })
            current += timedelta(seconds=bin_seconds)

        return result

    def threat_map_aggregate(
        self,
        *,
        since: datetime,
        until: datetime,
    ) -> List[Dict[str, Any]]:
        """Aggregate threat-map data by MITRE technique.

        Args:
            since: Inclusive lower bound.
            until: Exclusive upper bound.

        Returns:
            List of dicts: {technique, hit_count, severity_max, last_seen}
        """
        since_iso = _iso(since)
        until_iso = _iso(until)

        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    json_extract(t.value, '$') AS technique,
                    COUNT(*) AS hit_count,
                    MAX(CASE
                        WHEN severity = 'escalate' THEN 'escalate'
                        WHEN severity = 'review' THEN 'review'
                        ELSE 'observe'
                    END) AS severity_max,
                    MAX(ingested_at) AS last_seen
                FROM detections d, json_each(d.mitre_techniques) t
                WHERE d.ingested_at >= ? AND d.ingested_at < ?
                GROUP BY technique
                """,
                (since_iso, until_iso),
            ).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Phase-2: Helpers shared across methods
    # ------------------------------------------------------------------

    def _record_event(
        self,
        conn: sqlite3.Connection,
        *,
        case_id: str,
        kind: str,
        payload: Mapping[str, Any],
        actor_id: str,
    ) -> str:
        """Insert one ``case_events`` row.  Caller commits.

        Uses :func:`_iso_precise` (microsecond-precision ISO-8601) so events
        emitted within the same wall-clock second still sort deterministically
        in :meth:`list_case_events`.
        """

        event_id = _new_id()
        now_iso = _iso_precise(_utc_now())
        conn.execute(
            """
            INSERT INTO case_events (id, case_id, kind, payload_json, actor_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, case_id, kind, json.dumps(dict(payload), default=str), actor_id, now_iso),
        )
        return event_id

    def _refresh_severity_rollup(self, conn: sqlite3.Connection, case_id: str) -> None:
        rows = conn.execute(
            """
            SELECT d.severity FROM case_detections cd
            JOIN detections d ON d.id = cd.detection_id
            WHERE cd.case_id = ?
            """,
            (case_id,),
        ).fetchall()
        rollup = _max_severity([r["severity"] for r in rows]) if rows else "observe"
        conn.execute(
            "UPDATE cases SET severity_rollup = ? WHERE id = ?",
            (rollup, case_id),
        )

    def _fetch_case(self, case_id: str) -> CaseRow:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT c.*,
                       (SELECT COUNT(*) FROM case_detections cd
                        WHERE cd.case_id = c.id) AS detection_count
                FROM cases c WHERE c.id = ?
                """,
                (case_id,),
            ).fetchone()
        if row is None:
            raise NotFound(f"case '{case_id}' not found")
        return self._row_to_case(row)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_obj(row: sqlite3.Row) -> DetectionRow:
        try:
            techniques = json.loads(row["mitre_techniques"]) if row["mitre_techniques"] else []
        except (TypeError, json.JSONDecodeError):
            techniques = []
        try:
            payload = json.loads(row["layer_payload"]) if row["layer_payload"] else {}
        except (TypeError, json.JSONDecodeError):
            payload = {}
        return DetectionRow(
            id=row["id"],
            ingested_at=_parse_iso(row["ingested_at"]),
            event_id=row["event_id"],
            function_id=row["function_id"],
            anomaly_type=row["anomaly_type"],
            severity=row["severity"],
            trust_score=float(row["trust_score"] or 0.0),
            mitre_techniques=list(techniques),
            decision=row["decision"],
            risk_band=row["risk_band"],
            duration_ms=float(row["duration_ms"] or 0.0),
            correlation_id=row["correlation_id"],
            layer_payload=payload,
        )

    @staticmethod
    def _row_to_case(row: sqlite3.Row) -> CaseRow:
        keys = row.keys()
        return CaseRow(
            id=row["id"],
            title=row["title"],
            status=row["status"],
            severity_rollup=row["severity_rollup"],
            assignee_id=row["assignee_id"],
            opened_at=_parse_iso(row["opened_at"]),
            closed_at=_parse_iso(row["closed_at"]) if row["closed_at"] else None,
            created_by=row["created_by"],
            version=int(row["version"]),
            detection_count=int(row["detection_count"]) if "detection_count" in keys else 0,
        )

    @staticmethod
    def _row_to_comment(row: sqlite3.Row) -> CommentRow:
        return CommentRow(
            id=row["id"],
            case_id=row["case_id"],
            author_id=row["author_id"],
            body_md=row["body_md"],
            created_at=_parse_iso(row["created_at"]),
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> CaseEventRow:
        try:
            payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
        except (TypeError, json.JSONDecodeError):
            payload = {}
        return CaseEventRow(
            id=row["id"],
            case_id=row["case_id"],
            kind=row["kind"],
            payload=payload,
            actor_id=row["actor_id"],
            created_at=_parse_iso(row["created_at"]),
        )

    @staticmethod
    def _row_to_view(row: sqlite3.Row) -> SavedViewRow:
        try:
            filter_json = json.loads(row["filter_json"]) if row["filter_json"] else {}
        except (TypeError, json.JSONDecodeError):
            filter_json = {}
        try:
            sort_json = json.loads(row["sort_json"]) if row["sort_json"] else []
        except (TypeError, json.JSONDecodeError):
            sort_json = []
        return SavedViewRow(
            id=row["id"],
            name=row["name"],
            owner_id=row["owner_id"],
            filter_json=filter_json,
            sort_json=sort_json,
            created_at=_parse_iso(row["created_at"]),
            updated_at=_parse_iso(row["updated_at"]),
            pinned=bool(row["pinned"]),
        )

    # ------------------------------------------------------------------
    # Phase 4 — audit_events
    # ------------------------------------------------------------------

    def append_audit_event(
        self,
        *,
        actor_id: str,
        subject_kind: str,
        subject_id: Optional[str],
        action: str,
        payload_json: str,
        prev_hash: str,
        row_hash: str,
        event_id: Optional[str] = None,
        ts: Optional[datetime] = None,
    ) -> "AuditEventRow":
        """Append one immutable audit row.  Called ONLY from :mod:`.audit`."""
        row_id = event_id or _new_id()
        row_ts = ts or _utc_now()
        ts_str = _iso_precise(row_ts)
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO audit_events
                   (id, ts, actor_id, subject_kind, subject_id, action,
                    payload_json, prev_hash, row_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row_id, ts_str, actor_id, subject_kind, subject_id, action,
                 payload_json, prev_hash, row_hash),
            )
            conn.commit()
        try:
            payload = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            payload = {}
        return AuditEventRow(
            id=row_id, ts=row_ts, actor_id=actor_id, subject_kind=subject_kind,
            subject_id=subject_id, action=action, payload=payload,
            prev_hash=prev_hash, row_hash=row_hash,
        )

    def last_audit_row_hash(self) -> Optional[str]:
        """Return the ``row_hash`` of the most recent :data:`audit_events` row."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT row_hash FROM audit_events ORDER BY ts DESC, id DESC LIMIT 1"
            ).fetchone()
        return row["row_hash"] if row else None

    def list_audit_events(
        self,
        *,
        actor_id: Optional[str] = None,
        subject_kind: Optional[str] = None,
        action: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List["AuditEventRow"], int]:
        """Return ``(items, total)`` of audit events matching filters."""
        clauses: List[str] = []
        params: List[Any] = []
        if actor_id:
            clauses.append("actor_id = ?"); params.append(actor_id)
        if subject_kind:
            clauses.append("subject_kind = ?"); params.append(subject_kind)
        if action:
            clauses.append("action = ?"); params.append(action)
        if since:
            clauses.append("ts >= ?"); params.append(_iso_precise(since))
        if until:
            clauses.append("ts <= ?"); params.append(_iso_precise(until))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock, self._connect() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM audit_events {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM audit_events {where} "
                "ORDER BY ts DESC, id DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        items = []
        for r in rows:
            try:
                payload = json.loads(r["payload_json"])
            except (TypeError, json.JSONDecodeError):
                payload = {}
            items.append(AuditEventRow(
                id=r["id"], ts=_parse_iso(r["ts"]), actor_id=r["actor_id"],
                subject_kind=r["subject_kind"], subject_id=r["subject_id"],
                action=r["action"], payload=payload,
                prev_hash=r["prev_hash"], row_hash=r["row_hash"],
            ))
        return items, total

    def get_audit_event(self, event_id: str) -> Optional["AuditEventRow"]:
        """Return one audit event by ``id``, or ``None``."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM audit_events WHERE id = ?", (event_id,)
            ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            payload = {}
        return AuditEventRow(
            id=row["id"], ts=_parse_iso(row["ts"]), actor_id=row["actor_id"],
            subject_kind=row["subject_kind"], subject_id=row["subject_id"],
            action=row["action"], payload=payload,
            prev_hash=row["prev_hash"], row_hash=row["row_hash"],
        )

    def count_audit_events(self) -> int:
        """Return the total number of audit_events rows."""
        with self._lock, self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]

    def list_audit_distinct_actors(self) -> List[str]:
        """Return sorted list of distinct actor_ids in audit_events."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT actor_id FROM audit_events ORDER BY actor_id"
            ).fetchall()
        return [r["actor_id"] for r in rows]

    def verify_audit_chain(self) -> "ChainVerification":
        """Recompute SHA-256 hash chain over all audit_events.

        Walks rows ordered by ``ts ASC, id ASC``, re-derives ``row_hash``
        from the canonical body, and compares it to the stored value.

        Returns
        -------
        ChainVerification
            ``ok=True`` when every row's hash is consistent.
        """
        import hashlib
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_events ORDER BY ts ASC, id ASC"
            ).fetchall()
        if not rows:
            return ChainVerification(ok=True, total_rows=0)
        prev_hash = "0" * 64
        last_verified_id: Optional[str] = None
        for r in rows:
            body = json.dumps(
                {
                    "id": r["id"],
                    "ts": r["ts"],
                    "actor_id": r["actor_id"],
                    "subject_kind": r["subject_kind"],
                    "subject_id": r["subject_id"],
                    "action": r["action"],
                    "payload_json": r["payload_json"],
                    "prev_hash": prev_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            expected_hash = hashlib.sha256(body).hexdigest()
            if r["prev_hash"] != prev_hash or r["row_hash"] != expected_hash:
                return ChainVerification(
                    ok=False,
                    last_verified_id=last_verified_id,
                    broken_at=r["id"],
                    total_rows=len(rows),
                )
            last_verified_id = r["id"]
            prev_hash = r["row_hash"]
        return ChainVerification(ok=True, last_verified_id=last_verified_id, total_rows=len(rows))

    def vacuum_audit_events(self, max_rows: int = 100_000) -> int:
        """Delete oldest rows if ``audit_events`` exceeds *max_rows*.

        Returns the count of rows deleted.
        """
        with self._lock, self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
            if total <= max_rows:
                return 0
            to_delete = total - max_rows
            conn.execute(
                """DELETE FROM audit_events WHERE id IN (
                   SELECT id FROM audit_events ORDER BY ts ASC, id ASC LIMIT ?)""",
                (to_delete,),
            )
            conn.commit()
        return to_delete


# ---------------------------------------------------------------------------
# DTO projection helpers
# ---------------------------------------------------------------------------


def detection_to_summary_dict(row: DetectionRow) -> Dict[str, Any]:
    """Materialise the ``DetectionSummary`` shape from a :class:`DetectionRow`."""

    return {
        "id": row.id,
        "ingested_at": row.ingested_at,
        "event_id": row.event_id,
        "function_id": row.function_id,
        "anomaly_type": row.anomaly_type,
        "severity": row.severity,
        "trust_score": row.trust_score,
        "mitre_techniques": list(row.mitre_techniques),
        "decision": row.decision,
        "risk_band": row.risk_band,
    }


def detection_to_detail_dict(row: DetectionRow) -> Dict[str, Any]:
    base = detection_to_summary_dict(row)
    base["layer_payload"] = row.layer_payload
    return base


def case_to_summary_dict(row: CaseRow) -> Dict[str, Any]:
    """Compact case view used in CaseBadge, list endpoints, and SSE frames."""

    return {
        "id": row.id,
        "title": row.title,
        "status": row.status,
        "severity_rollup": row.severity_rollup,
        "assignee_id": row.assignee_id,
        "opened_at": row.opened_at,
        "closed_at": row.closed_at,
        "detection_count": row.detection_count,
    }


def case_to_dict(row: CaseRow) -> Dict[str, Any]:
    """Full case payload (Detail tab)."""

    return {
        "id": row.id,
        "title": row.title,
        "status": row.status,
        "severity_rollup": row.severity_rollup,
        "assignee_id": row.assignee_id,
        "opened_at": row.opened_at,
        "closed_at": row.closed_at,
        "created_by": row.created_by,
        "version": row.version,
        "detection_count": row.detection_count,
    }


def comment_to_dict(row: CommentRow) -> Dict[str, Any]:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "author_id": row.author_id,
        "body_md": row.body_md,
        "created_at": row.created_at,
    }


def case_event_to_dict(row: CaseEventRow) -> Dict[str, Any]:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "kind": row.kind,
        "payload": row.payload,
        "actor_id": row.actor_id,
        "created_at": row.created_at,
    }


def saved_view_to_dict(row: SavedViewRow) -> Dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "owner_id": row.owner_id,
        "filter_json": row.filter_json,
        "sort_json": row.sort_json,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "pinned": row.pinned,
    }


__all__ = [
    "DetectionStore",
    "DetectionRow",
    "CaseRow",
    "CommentRow",
    "CaseEventRow",
    "SavedViewRow",
    "FunctionRollupRow",
    "FunctionDetailRows",
    "AuditEventRow",
    "ChainVerification",
    "StoreError",
    "NotFound",
    "VersionConflict",
    "DuplicateAttachment",
    "AlreadyAttached",
    "detection_to_summary_dict",
    "detection_to_detail_dict",
    "case_to_summary_dict",
    "case_to_dict",
    "comment_to_dict",
    "case_event_to_dict",
    "saved_view_to_dict",
]
