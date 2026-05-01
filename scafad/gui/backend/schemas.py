"""Pydantic v2 DTOs for the SCAFAD GUI HTTP API.

These mirror the structures consumed by the React frontend.  The
``layer_payload`` field of :class:`DetectionDetail` carries the full
:class:`scafad.runtime.runtime.CanonicalRuntimeResult.to_dict()` blob so the
DetectionDetail page can render every layer of the evidence trail without a
second round trip.

Phase 2 adds DTOs for the case-management surface:
:class:`Case`, :class:`CaseSummary`, :class:`Comment`, :class:`CaseEvent`,
:class:`SavedView`, plus inbox aggregates and bulk-action contracts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Health / system status
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    ok: bool = True
    version: str
    commit: str
    started_at: datetime
    env: str = "dev"
    db_path: str


class LayerStatus(BaseModel):
    layer: str
    healthy: bool = True
    description: str
    detector_count: int = 0


class SystemStatusResponse(BaseModel):
    layers: List[LayerStatus]
    detector_count: int
    db_size_bytes: int
    last_ingest_at: Optional[datetime] = None
    detections_total: int


# ---------------------------------------------------------------------------
# Ingest contract
# ---------------------------------------------------------------------------


class IngestRequest(BaseModel):
    """A SCAFAD event payload to be passed straight into the runtime."""

    model_config = ConfigDict(extra="allow")

    event_id: Optional[str] = None
    function_id: Optional[str] = None
    anomaly: Optional[str] = Field(default=None, alias="anomaly_type")
    execution_phase: Optional[str] = None
    duration: Optional[float] = None
    memory_spike_kb: Optional[int] = None
    cpu_utilization: Optional[float] = None
    network_io_bytes: Optional[int] = None
    region: Optional[str] = None

    def to_event(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=False, exclude_none=False)


class IngestResponse(BaseModel):
    id: str
    severity: str
    anomaly_type: str
    mitre_techniques: List[str]


# ---------------------------------------------------------------------------
# Phase 2 — case management
# ---------------------------------------------------------------------------


CaseStatus = Literal["open", "triage", "contained", "closed"]


class CaseSummary(BaseModel):
    """Compact view used for CaseBadge, list endpoints, and SSE frames."""

    id: str
    title: str
    status: CaseStatus
    severity_rollup: str
    assignee_id: Optional[str] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None
    detection_count: int = 0


class Case(BaseModel):
    """Full case payload."""

    id: str
    title: str
    status: CaseStatus
    severity_rollup: str
    assignee_id: Optional[str] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None
    created_by: str
    version: int
    detection_count: int = 0


class CaseListResponse(BaseModel):
    items: List[CaseSummary]
    total: int
    page: int = 1
    page_size: int = 50


class CaseCreate(BaseModel):
    title: str
    detection_ids: List[str] = Field(default_factory=list)
    assignee_id: Optional[str] = None
    status: CaseStatus = "open"


class CaseUpdate(BaseModel):
    expected_version: int
    title: Optional[str] = None
    status: Optional[CaseStatus] = None
    assignee_id: Optional[str] = None
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 2 — comments
# ---------------------------------------------------------------------------


class Comment(BaseModel):
    id: str
    case_id: str
    author_id: str
    body_md: str
    created_at: datetime


class CommentCreate(BaseModel):
    body_md: str


class CommentListResponse(BaseModel):
    items: List[Comment]
    total: int


# ---------------------------------------------------------------------------
# Phase 2 — case events
# ---------------------------------------------------------------------------


CaseEventKind = Literal[
    "created",
    "state_changed",
    "assigned",
    "commented",
    "detection_attached",
    "detection_detached",
    "dismissed",
    "reopened",
]


class CaseEvent(BaseModel):
    id: str
    case_id: str
    kind: CaseEventKind
    payload: Dict[str, Any] = Field(default_factory=dict)
    actor_id: str
    created_at: datetime


class CaseEventListResponse(BaseModel):
    items: List[CaseEvent]
    total: int


# ---------------------------------------------------------------------------
# Phase 2 — saved views
# ---------------------------------------------------------------------------


class SavedView(BaseModel):
    id: str
    name: str
    owner_id: str
    filter_json: Dict[str, Any] = Field(default_factory=dict)
    sort_json: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    pinned: bool = False


class SavedViewCreate(BaseModel):
    name: str
    filter_json: Dict[str, Any] = Field(default_factory=dict)
    sort_json: List[Dict[str, Any]] = Field(default_factory=list)
    pinned: bool = False


class SavedViewUpdate(BaseModel):
    name: Optional[str] = None
    filter_json: Optional[Dict[str, Any]] = None
    sort_json: Optional[List[Dict[str, Any]]] = None
    pinned: Optional[bool] = None


class SavedViewListResponse(BaseModel):
    items: List[SavedView]
    total: int


# ---------------------------------------------------------------------------
# Phase 2 — bulk actions
# ---------------------------------------------------------------------------


BulkActionType = Literal[
    "assign",
    "dismiss",
    "attach",
    "open_case",
]


class BulkActionRequest(BaseModel):
    """The body posted to ``POST /api/inbox/bulk_action``.

    The interpretation of ``payload`` depends on ``action``:

    * ``assign`` → ``{"assignee_id": "<user-id-or-empty>"}`` (Phase 2 records
      this as a case-only operation; for unattached detections the action is a
      no-op so the test surface is well defined).
    * ``dismiss`` → ``{"reason": "<text>"}`` — for unattached detections this
      currently records a dismiss event only when a case exists.
    * ``attach``  → ``{"case_id": "<case-id>"}`` — attaches each detection to
      the case (each item independently; per-item errors are reported in the
      response).
    * ``open_case`` → ``{"title": "<title>", "assignee_id": "..."}`` — opens
      a new case with the supplied detections.
    """

    action: BulkActionType
    detection_ids: List[str]
    payload: Dict[str, Any] = Field(default_factory=dict)


class BulkActionResult(BaseModel):
    id: str
    ok: bool
    error: Optional[str] = None


class BulkActionResponse(BaseModel):
    action: BulkActionType
    results: List[BulkActionResult]
    succeeded: int
    failed: int
    case_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 2 — inbox summary
# ---------------------------------------------------------------------------


class TechniqueCount(BaseModel):
    technique: str
    count: int


class CaseStatusCounts(BaseModel):
    open: int = 0
    triage: int = 0
    contained: int = 0
    closed: int = 0
    none: int = 0


class InboxSummary(BaseModel):
    """Filter-aware aggregates for the Inbox sticky header."""

    total: int
    severity_counts: "SeverityMix"
    case_status_counts: CaseStatusCounts
    top_mitre: List[TechniqueCount] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Detection list / detail
# ---------------------------------------------------------------------------


class DetectionSummary(BaseModel):
    """Compact row consumed by tables and SSE feed updates."""

    id: str
    ingested_at: datetime
    event_id: str
    function_id: str
    anomaly_type: str
    severity: str
    trust_score: float
    mitre_techniques: List[str] = Field(default_factory=list)
    decision: Optional[str] = None
    risk_band: Optional[str] = None


class DetectionListResponse(BaseModel):
    items: List[DetectionSummary]
    total: int
    page: int = 1
    page_size: int = 50


class DetectionDetail(BaseModel):
    """Full evidence trail for the DetectionDetail page.

    Phase 2 adds an OPTIONAL ``case`` field that surfaces the linked
    :class:`CaseSummary` when the detection has been attached.  Phase-1
    callers that drop unknown fields are unaffected.
    """

    id: str
    ingested_at: datetime
    event_id: str
    function_id: str
    anomaly_type: str
    severity: str
    trust_score: float
    mitre_techniques: List[str]
    decision: Optional[str] = None
    risk_band: Optional[str] = None
    layer_payload: Mapping[str, Any]
    case: Optional[CaseSummary] = None


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------


class SeverityMix(BaseModel):
    observe: int = 0
    review: int = 0
    escalate: int = 0


class HistogramBucket(BaseModel):
    hour: str
    observe: int = 0
    review: int = 0
    escalate: int = 0


class DashboardSummary(BaseModel):
    open_count: int
    severity_mix: SeverityMix
    ingest_rate_1h: int
    layer_p95_ms: float
    hist24h: List[HistogramBucket]


# Resolve forward reference now that SeverityMix is defined.
InboxSummary.model_rebuild()


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — Function Inventory and Threat Map
# ─────────────────────────────────────────────────────────────────────────────


class FunctionRollup(BaseModel):
    """One row in the Functions page list."""

    function_id: str
    last_seen: datetime
    count_24h: int
    count_7d: int
    severity_max: str  # "observe", "review", "escalate"
    open_case_count: int
    top_mitre: List[str] = Field(default_factory=list)  # Top 3 techniques


class FunctionListResponse(BaseModel):
    """Response for GET /api/functions."""

    items: List[FunctionRollup]
    total: int
    limit: int
    offset: int


class SparklineBin(BaseModel):
    """A single histogram bin for the sparkline."""

    bucket_start: str  # ISO-8601 datetime
    count: int
    severity_max: Optional[str] = None


class MitreChip(BaseModel):
    """A MITRE technique with count."""

    id: str
    count: int


class LinkedCaseSummary(BaseModel):
    """A case linked from a function detail."""

    case_id: str
    title: str
    status: str
    severity_rollup: str


class FunctionDetail(BaseModel):
    """Response for GET /api/functions/{function_id}."""

    function_id: str
    severity_counts: Dict[str, int]  # severity → count
    mitre_counts: Dict[str, int]  # technique_id → count
    top_mitre: List[MitreChip]
    sparkline: List[SparklineBin]
    recent_detections: List[DetectionSummary]
    linked_cases: List[LinkedCaseSummary]


class TechniqueDef(BaseModel):
    """A MITRE technique definition."""

    id: str
    name: str
    description: str


class TacticDef(BaseModel):
    """A tactic and its techniques."""

    tactic: str
    techniques: List[TechniqueDef]


class ThreatMapCell(BaseModel):
    """A single heatmap cell."""

    technique_id: str
    count: int
    severity_max: Optional[str] = None
    last_seen: Optional[datetime] = None


class ThreatMapMatrix(BaseModel):
    """Nested matrix: matrix[tactic][technique_id] = ThreatMapCell."""

    matrix: Dict[str, Dict[str, ThreatMapCell]]


class ThreatMapResponse(BaseModel):
    """Response for GET /api/threat-map."""

    matrix: Dict[str, Dict[str, ThreatMapCell]]
    window_spec: str  # "24h", "7d", "30d", "custom"
    since: str  # ISO-8601 datetime
    until: str  # ISO-8601 datetime


class ThreatMapGridResponse(BaseModel):
    """Response for GET /api/threat-map/grid (static vocabulary)."""

    tactics: Dict[str, List[TechniqueDef]]


# ---------------------------------------------------------------------------
# Phase 4 — System Status (live per-layer metrics)
# ---------------------------------------------------------------------------


class LayerStatusExtended(LayerStatus):
    """Phase-1 :class:`LayerStatus` extended with live latency metrics (Phase 4)."""

    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    error_rate_pct: float = 0.0
    recent_count: int = 0
    last_error_at: Optional[datetime] = None


class SystemMetricsResponse(BaseModel):
    """System-wide aggregate snapshot (extends :class:`SystemStatusResponse` in Phase 4)."""

    layers: List[LayerStatusExtended]
    detector_count: int
    db_size_bytes: int
    last_ingest_at: Optional[datetime] = None
    detections_total: int
    audit_events_total: int = 0
    runtime_warmed: bool = False


class TimeseriesPoint(BaseModel):
    """One time-bin of per-layer metrics."""

    ts: datetime
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    error_rate_pct: float = 0.0
    count: int = 0


class MetricsTimeseriesResponse(BaseModel):
    """Per-layer latency timeseries for a given time window."""

    window_spec: str
    bin: str
    series: Dict[str, List[TimeseriesPoint]]


# ---------------------------------------------------------------------------
# Phase 4 — Detector Panel
# ---------------------------------------------------------------------------


class DetectorEntry(BaseModel):
    """One L0 detector with its current config."""

    id: str
    weight: float = 1.0
    threshold: Optional[float] = None
    last_signal_at: Optional[datetime] = None


class DetectorPanel(BaseModel):
    """Full detector panel (``available=False`` before first ingest)."""

    available: bool
    detectors: List[DetectorEntry]


# ---------------------------------------------------------------------------
# Phase 4 — Settings (read-only)
# ---------------------------------------------------------------------------


class RedactionPolicy(BaseModel):
    """Read-only projection of the active redaction / retention policy."""

    rules: List[Dict[str, Any]] = Field(default_factory=list)
    retention_days: int = 365


class FusionWeights(BaseModel):
    """Fusion-layer weights and risk-band thresholds."""

    layer_weights: Dict[str, float] = Field(default_factory=dict)
    risk_band_thresholds: Dict[str, float] = Field(default_factory=dict)


class RuntimeRuntimeConfig(BaseModel):
    """Read-only snapshot of runtime detector config."""

    available: bool
    detector_panel: "DetectorPanel"
    fusion: "FusionWeights"


class GUIConfigSnapshot(BaseModel):
    """Sanitised, read-only projection of :class:`~.config.GUISettings` (no secrets)."""

    env: str
    host: str
    port: int
    cors_origins: List[str]
    version: str
    commit: str
    sse_keepalive_seconds: float
    db_path: str


class SettingsResponse(BaseModel):
    """Combined read-only settings response."""

    runtime: "RuntimeRuntimeConfig"
    policy: "RedactionPolicy"
    gui: "GUIConfigSnapshot"


# ---------------------------------------------------------------------------
# Phase 4 — Audit Log (hash-chained)
# ---------------------------------------------------------------------------


class AuditEvent(BaseModel):
    """One row from ``audit_events`` (hash chain)."""

    id: str
    ts: datetime
    actor_id: str
    subject_kind: Literal[
        "detection", "case", "view", "inbox_bulk", "ingest", "system", "comment"
    ]
    subject_id: Optional[str] = None
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    row_hash: str


class AuditEventListResponse(BaseModel):
    """Paginated list of audit events."""

    items: List["AuditEvent"]
    total: int
    page: int = 1
    page_size: int = 50


class AuditChainVerification(BaseModel):
    """Result of the hash-chain integrity check."""

    ok: bool
    last_verified_id: Optional[str] = None
    broken_at: Optional[str] = None
    total_rows: int = 0


__all__ = [
    "HealthResponse",
    "LayerStatus",
    "SystemStatusResponse",
    "IngestRequest",
    "IngestResponse",
    "DetectionSummary",
    "DetectionListResponse",
    "DetectionDetail",
    "SeverityMix",
    "HistogramBucket",
    "DashboardSummary",
    # Phase 2
    "CaseStatus",
    "CaseSummary",
    "Case",
    "CaseListResponse",
    "CaseCreate",
    "CaseUpdate",
    "Comment",
    "CommentCreate",
    "CommentListResponse",
    "CaseEvent",
    "CaseEventKind",
    "CaseEventListResponse",
    "SavedView",
    "SavedViewCreate",
    "SavedViewUpdate",
    "SavedViewListResponse",
    "BulkActionType",
    "BulkActionRequest",
    "BulkActionResult",
    "BulkActionResponse",
    "TechniqueCount",
    "CaseStatusCounts",
    "InboxSummary",
    # Phase 3
    "FunctionRollup",
    "FunctionListResponse",
    "SparklineBin",
    "MitreChip",
    "LinkedCaseSummary",
    "FunctionDetail",
    "TechniqueDef",
    "TacticDef",
    "ThreatMapCell",
    "ThreatMapMatrix",
    "ThreatMapResponse",
    "ThreatMapGridResponse",
    # Phase 4
    "LayerStatusExtended",
    "SystemMetricsResponse",
    "TimeseriesPoint",
    "MetricsTimeseriesResponse",
    "DetectorEntry",
    "DetectorPanel",
    "RedactionPolicy",
    "FusionWeights",
    "RuntimeRuntimeConfig",
    "GUIConfigSnapshot",
    "SettingsResponse",
    "AuditEvent",
    "AuditEventListResponse",
    "AuditChainVerification",
]
