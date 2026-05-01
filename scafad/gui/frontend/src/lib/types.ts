/**
 * TypeScript mirrors of the Pydantic DTOs in
 * `scafad/gui/backend/schemas.py`. Drift is checked by
 * `tests/unit/test_gui_backend_dto_parity.py`.
 *
 * Phase 2 adds the case-management surface: Case, Comment, CaseEvent,
 * SavedView, BulkActionRequest/Response, InboxSummary.
 */

export type Severity = "observe" | "review" | "escalate";

export type CaseStatus = "open" | "triage" | "contained" | "closed";

export type CaseEventKind =
  | "created"
  | "state_changed"
  | "assigned"
  | "commented"
  | "detection_attached"
  | "detection_detached"
  | "dismissed"
  | "reopened";

export type BulkActionType = "assign" | "dismiss" | "attach" | "open_case";

export interface HealthResponse {
  ok: boolean;
  version: string;
  commit: string;
  started_at: string;
  env: string;
  db_path: string;
}

export interface LayerStatus {
  layer: string;
  healthy: boolean;
  description: string;
  detector_count: number;
}

export interface SystemStatusResponse {
  layers: LayerStatus[];
  detector_count: number;
  db_size_bytes: number;
  last_ingest_at: string | null;
  detections_total: number;
}

export interface DetectionSummary {
  id: string;
  ingested_at: string;
  event_id: string;
  function_id: string;
  anomaly_type: string;
  severity: Severity;
  trust_score: number;
  mitre_techniques: string[];
  decision: string | null;
  risk_band: string | null;
}

export interface DetectionListResponse {
  items: DetectionSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface SeverityMix {
  observe: number;
  review: number;
  escalate: number;
}

export interface HistogramBucket {
  hour: string;
  observe: number;
  review: number;
  escalate: number;
}

export interface DashboardSummary {
  open_count: number;
  severity_mix: SeverityMix;
  ingest_rate_1h: number;
  layer_p95_ms: number;
  hist24h: HistogramBucket[];
}

export interface LayerEvidencePayload {
  layer0_record: Record<string, unknown>;
  adapted_record: Record<string, unknown>;
  layer1_record: Record<string, unknown>;
  multilayer_result: {
    layer1: Record<string, unknown>;
    layer2: Record<string, unknown>;
    layer3: Record<string, unknown>;
    layer4: Record<string, unknown>;
    layer5: Record<string, unknown>;
    layer6: Record<string, unknown> | null;
  };
}

export interface DetectionDetail extends DetectionSummary {
  layer_payload: LayerEvidencePayload;
  case?: CaseSummary | null;
}

export interface IngestRequest {
  event_id?: string;
  function_id?: string;
  anomaly?: string;
  execution_phase?: string;
  duration?: number;
  memory_spike_kb?: number;
  cpu_utilization?: number;
  network_io_bytes?: number;
  region?: string;
  [key: string]: unknown;
}

export interface IngestResponse {
  id: string;
  severity: Severity;
  anomaly_type: string;
  mitre_techniques: string[];
}

// ---------------------------------------------------------------------------
// Phase 2 — cases
// ---------------------------------------------------------------------------

export interface CaseSummary {
  id: string;
  title: string;
  status: CaseStatus;
  severity_rollup: string;
  assignee_id: string | null;
  opened_at: string;
  closed_at: string | null;
  detection_count: number;
}

export interface Case {
  id: string;
  title: string;
  status: CaseStatus;
  severity_rollup: string;
  assignee_id: string | null;
  opened_at: string;
  closed_at: string | null;
  created_by: string;
  version: number;
  detection_count: number;
}

export interface CaseListResponse {
  items: CaseSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface CaseCreate {
  title: string;
  detection_ids?: string[];
  assignee_id?: string | null;
  status?: CaseStatus;
}

export interface CaseUpdate {
  expected_version: number;
  title?: string;
  status?: CaseStatus;
  assignee_id?: string | null;
  reason?: string;
}

// ---------------------------------------------------------------------------
// Phase 2 — comments
// ---------------------------------------------------------------------------

export interface Comment {
  id: string;
  case_id: string;
  author_id: string;
  body_md: string;
  created_at: string;
}

export interface CommentCreate {
  body_md: string;
}

export interface CommentListResponse {
  items: Comment[];
  total: number;
}

// ---------------------------------------------------------------------------
// Phase 2 — case events
// ---------------------------------------------------------------------------

export interface CaseEvent {
  id: string;
  case_id: string;
  kind: CaseEventKind;
  payload: Record<string, unknown>;
  actor_id: string;
  created_at: string;
}

export interface CaseEventListResponse {
  items: CaseEvent[];
  total: number;
}

// ---------------------------------------------------------------------------
// Phase 2 — saved views
// ---------------------------------------------------------------------------

export interface SavedView {
  id: string;
  name: string;
  owner_id: string;
  filter_json: Record<string, unknown>;
  sort_json: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
  pinned: boolean;
}

export interface SavedViewCreate {
  name: string;
  filter_json?: Record<string, unknown>;
  sort_json?: Array<Record<string, unknown>>;
  pinned?: boolean;
}

export interface SavedViewUpdate {
  name?: string;
  filter_json?: Record<string, unknown>;
  sort_json?: Array<Record<string, unknown>>;
  pinned?: boolean;
}

export interface SavedViewListResponse {
  items: SavedView[];
  total: number;
}

// ---------------------------------------------------------------------------
// Phase 2 — bulk actions
// ---------------------------------------------------------------------------

export interface BulkActionRequest {
  action: BulkActionType;
  detection_ids: string[];
  payload?: Record<string, unknown>;
}

export interface BulkActionResult {
  id: string;
  ok: boolean;
  error?: string | null;
}

export interface BulkActionResponse {
  action: BulkActionType;
  results: BulkActionResult[];
  succeeded: number;
  failed: number;
  case_id: string | null;
}

// ---------------------------------------------------------------------------
// Phase 2 — inbox summary
// ---------------------------------------------------------------------------

export interface TechniqueCount {
  technique: string;
  count: number;
}

export interface CaseStatusCounts {
  open: number;
  triage: number;
  contained: number;
  closed: number;
  none: number;
}

export interface InboxSummary {
  total: number;
  severity_counts: SeverityMix;
  case_status_counts: CaseStatusCounts;
  top_mitre: TechniqueCount[];
}

// ---------------------------------------------------------------------------
// Phase 2 — Inbox filter state (frontend-only)
// ---------------------------------------------------------------------------

export interface InboxFilters {
  severity?: Severity[];
  anomaly_type?: string[];
  mitre_technique?: string[];
  function_id?: string;
  decision?: string[];
  risk_band?: string[];
  text?: string;
  since?: string;
  until?: string;
  case_status?: CaseStatus | "none";
}

// ---------------------------------------------------------------------------
// Phase 3 — Functions
// ---------------------------------------------------------------------------

export interface FunctionRollup {
  function_id: string;
  last_seen: string;
  count_24h: number;
  count_7d: number;
  severity_max: string;
  open_case_count: number;
  top_mitre: string[];
}

export interface FunctionListResponse {
  items: FunctionRollup[];
  total: number;
  limit: number;
  offset: number;
}

export interface SparklineBin {
  bucket_start: string;
  count: number;
  severity_max?: string;
}

export interface MitreChip {
  id: string;
  count: number;
}

export interface LinkedCaseSummary {
  case_id: string;
  title: string;
  status: CaseStatus;
  severity_rollup: string;
}

export interface FunctionDetail {
  function_id: string;
  severity_counts: Record<string, number>;
  mitre_counts: Record<string, number>;
  top_mitre: MitreChip[];
  sparkline: SparklineBin[];
  recent_detections: DetectionSummary[];
  linked_cases: LinkedCaseSummary[];
}

// ---------------------------------------------------------------------------
// Phase 3 — Threat Map
// ---------------------------------------------------------------------------

export interface TechniqueDef {
  id: string;
  name: string;
  description: string;
}

export interface ThreatMapCell {
  technique_id: string;
  count: number;
  severity_max?: string;
  last_seen?: string;
}

export interface ThreatMapResponse {
  matrix: Record<string, Record<string, ThreatMapCell>>;
  window_spec: string;
  since: string;
  until: string;
}

export interface ThreatMapGridResponse {
  tactics: Record<string, TechniqueDef[]>;
}

// ---------------------------------------------------------------------------
// Phase 4 — System Status, Settings, Audit
// ---------------------------------------------------------------------------

export interface LayerStatusExtended extends LayerStatus {
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  error_rate_pct: number;
  recent_count: number;
  last_error_at: string | null;
}

export interface SystemMetricsResponse {
  layers: LayerStatusExtended[];
  detector_count: number;
  db_size_bytes: number;
  last_ingest_at: string | null;
  detections_total: number;
  audit_events_total: number;
  runtime_warmed: boolean;
}

export interface TimeseriesPoint {
  ts: string;
  p50_ms: number;
  p95_ms: number;
  error_rate_pct: number;
  count: number;
}

export interface MetricsTimeseriesResponse {
  window_spec: string;
  bin: string;
  series: Record<string, TimeseriesPoint[]>;
}

export interface DetectorEntry {
  id: string;
  weight: number;
  threshold: number | null;
  last_signal_at: string | null;
}

export interface DetectorPanel {
  available: boolean;
  detectors: DetectorEntry[];
}

export interface RedactionPolicy {
  rules: Record<string, unknown>[];
  retention_days: number;
}

export interface FusionWeights {
  layer_weights: Record<string, number>;
  risk_band_thresholds: Record<string, number>;
}

export interface RuntimeRuntimeConfig {
  available: boolean;
  detector_panel: DetectorPanel;
  fusion: FusionWeights;
}

export interface GUIConfigSnapshot {
  env: string;
  host: string;
  port: number;
  cors_origins: string[];
  version: string;
  commit: string;
  sse_keepalive_seconds: number;
  db_path: string;
}

export interface SettingsResponse {
  runtime: RuntimeRuntimeConfig;
  policy: RedactionPolicy;
  gui: GUIConfigSnapshot;
}

export type AuditSubjectKind = "detection" | "case" | "view" | "inbox_bulk" | "ingest" | "system" | "comment";

export interface AuditEvent {
  id: string;
  ts: string;
  actor_id: string;
  subject_kind: AuditSubjectKind;
  subject_id: string | null;
  action: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  row_hash: string;
}

export interface AuditEventListResponse {
  items: AuditEvent[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditChainVerification {
  ok: boolean;
  last_verified_id: string | null;
  broken_at: string | null;
  total_rows: number;
}

export interface AuditFilterOptions {
  actor_ids: string[];
  subject_kinds: AuditSubjectKind[];
  actions: string[];
}

// ---------------------------------------------------------------------------
// AWS Live Ingest
// ---------------------------------------------------------------------------

export interface AwsFunction {
  name: string;
  runtime: string;
  memory_size: number;
  timeout: number;
  last_modified: string;
  region: string;
}
