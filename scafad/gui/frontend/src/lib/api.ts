/**
 * Lightweight fetch wrapper + TanStack Query keys for the SCAFAD GUI.
 *
 * Phase 1 covered detections / health / system / ingest.  Phase 2 adds the
 * Cases, Inbox (summary + bulk + export), and Saved-Views surface plus a
 * dedicated SSE hook for case-channel invalidation.
 */

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type {
  AuditChainVerification,
  AuditEvent,
  AuditEventListResponse,
  AwsFunction,
  BulkActionRequest,
  BulkActionResponse,
  Case,
  CaseCreate,
  CaseEventListResponse,
  CaseListResponse,
  CaseSummary,
  CaseStatus,
  CaseUpdate,
  Comment,
  CommentCreate,
  CommentListResponse,
  DashboardSummary,
  DetectionDetail,
  DetectionListResponse,
  DetectionSummary,
  DetectorPanel,
  GUIConfigSnapshot,
  HealthResponse,
  InboxFilters,
  InboxSummary,
  IngestRequest,
  IngestResponse,
  MetricsTimeseriesResponse,
  RedactionPolicy,
  RuntimeRuntimeConfig,
  SavedView,
  SavedViewCreate,
  SavedViewListResponse,
  SavedViewUpdate,
  SettingsResponse,
  Severity,
  SystemMetricsResponse,
  SystemStatusResponse,
} from "./types";

const API_BASE = "/api";

/**
 * In-flight request cache: if the same GET request fires within 100ms,
 * return the same Promise. Prevents duplicate requests on React StrictMode
 * double-invocation and concurrent effects.
 */
const inFlightRequests = new Map<string, Promise<any>>();
const REQUEST_DEDUP_WINDOW_MS = 100;

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method?.toUpperCase() ?? "GET";
  const cacheKey = `${method}:${path}`;

  // For GET requests, check in-flight cache
  if (method === "GET" && inFlightRequests.has(cacheKey)) {
    return inFlightRequests.get(cacheKey)!;
  }

  // Create the fetch promise
  const fetchPromise = (async () => {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(`API ${response.status} ${response.statusText} — ${text}`);
    }
    // 204 No Content
    if (response.status === 204) {
      return undefined as unknown as T;
    }
    return (await response.json()) as T;
  })();

  // For GET requests, cache the in-flight promise
  if (method === "GET") {
    inFlightRequests.set(cacheKey, fetchPromise);

    // Auto-expire from cache after the dedup window
    fetchPromise
      .then(() => {
        setTimeout(() => {
          inFlightRequests.delete(cacheKey);
        }, REQUEST_DEDUP_WINDOW_MS);
      })
      .catch(() => {
        // On error, remove from cache immediately to allow retry
        inFlightRequests.delete(cacheKey);
      });
  }

  return fetchPromise;
}

// ---------------------------------------------------------------------------
// Query-string helpers
// ---------------------------------------------------------------------------

function appendFilters(qs: URLSearchParams, filters: InboxFilters | undefined): void {
  if (!filters) return;
  if (filters.severity && filters.severity.length === 1) {
    qs.set("severity", filters.severity[0]);
  }
  if (filters.anomaly_type && filters.anomaly_type.length === 1) {
    qs.set("anomaly_type", filters.anomaly_type[0]);
  }
  if (filters.mitre_technique && filters.mitre_technique.length === 1) {
    qs.set("mitre_technique", filters.mitre_technique[0]);
  }
  if (filters.function_id) qs.set("function_id", filters.function_id);
  if (filters.decision && filters.decision.length === 1) {
    qs.set("decision", filters.decision[0]);
  }
  if (filters.risk_band && filters.risk_band.length === 1) {
    qs.set("risk_band", filters.risk_band[0]);
  }
  if (filters.text) qs.set("text", filters.text);
  if (filters.since) qs.set("since", filters.since);
  if (filters.until) qs.set("until", filters.until);
  if (filters.case_status) qs.set("case_status", filters.case_status);
}

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------

export interface ListDetectionsOptions {
  filters?: InboxFilters;
  page?: number;
  page_size?: number;
}

export const api = {
  health: () => jsonFetch<HealthResponse>("/health"),
  systemStatus: () => jsonFetch<SystemStatusResponse>("/system/status"),
  // Phase 1 simple list (kept identical for backwards compat).
  listDetections: (
    filters: { severity?: Severity; anomaly_type?: string; since?: string; page_size?: number } = {}
  ) => {
    const qs = new URLSearchParams();
    if (filters.severity) qs.set("severity", filters.severity);
    if (filters.anomaly_type) qs.set("anomaly_type", filters.anomaly_type);
    if (filters.since) qs.set("since", filters.since);
    if (filters.page_size) qs.set("page_size", String(filters.page_size));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return jsonFetch<DetectionListResponse>(`/detections${suffix}`);
  },
  // Phase 2 rich list (used by Inbox).
  listInboxDetections: (opts: ListDetectionsOptions = {}) => {
    const qs = new URLSearchParams();
    appendFilters(qs, opts.filters);
    if (opts.page) qs.set("page", String(opts.page));
    if (opts.page_size) qs.set("page_size", String(opts.page_size));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return jsonFetch<DetectionListResponse>(`/detections${suffix}`);
  },
  getDetection: (id: string) => jsonFetch<DetectionDetail>(`/detections/${encodeURIComponent(id)}`),
  summary: () => jsonFetch<DashboardSummary>("/detections/summary"),
  ingest: (event: IngestRequest) =>
    jsonFetch<IngestResponse>("/ingest", { method: "POST", body: JSON.stringify(event) }),

  // ── Phase 2: cases ───────────────────────────────────────────────────
  listCases: (
    opts: { status?: CaseStatus; assignee_id?: string; page?: number; page_size?: number } = {}
  ) => {
    const qs = new URLSearchParams();
    if (opts.status) qs.set("status", opts.status);
    if (opts.assignee_id) qs.set("assignee_id", opts.assignee_id);
    if (opts.page) qs.set("page", String(opts.page));
    if (opts.page_size) qs.set("page_size", String(opts.page_size));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return jsonFetch<CaseListResponse>(`/cases${suffix}`);
  },
  getCase: (id: string) => jsonFetch<Case>(`/cases/${encodeURIComponent(id)}`),
  createCase: (body: CaseCreate) =>
    jsonFetch<Case>("/cases", { method: "POST", body: JSON.stringify(body) }),
  patchCase: (id: string, body: CaseUpdate) =>
    jsonFetch<Case>(`/cases/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteCase: (id: string) =>
    jsonFetch<void>(`/cases/${encodeURIComponent(id)}`, { method: "DELETE" }),
  attachDetections: (id: string, detection_ids: string[]) =>
    jsonFetch<BulkActionResponse>(`/cases/${encodeURIComponent(id)}/attach`, {
      method: "POST",
      body: JSON.stringify({ detection_ids }),
    }),
  detachDetections: (id: string, detection_ids: string[]) =>
    jsonFetch<BulkActionResponse>(`/cases/${encodeURIComponent(id)}/detach`, {
      method: "POST",
      body: JSON.stringify({ detection_ids }),
    }),
  listCaseEvents: (id: string) =>
    jsonFetch<CaseEventListResponse>(`/cases/${encodeURIComponent(id)}/events`),
  listComments: (id: string) =>
    jsonFetch<CommentListResponse>(`/cases/${encodeURIComponent(id)}/comments`),
  addComment: (id: string, body: CommentCreate) =>
    jsonFetch<Comment>(`/cases/${encodeURIComponent(id)}/comments`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listCaseDetections: (id: string) =>
    jsonFetch<DetectionListResponse>(`/cases/${encodeURIComponent(id)}/detections`),

  // ── Phase 2: views ───────────────────────────────────────────────────
  listViews: () => jsonFetch<SavedViewListResponse>("/views"),
  createView: (body: SavedViewCreate) =>
    jsonFetch<SavedView>("/views", { method: "POST", body: JSON.stringify(body) }),
  patchView: (id: string, body: SavedViewUpdate) =>
    jsonFetch<SavedView>(`/views/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteView: (id: string) =>
    jsonFetch<void>(`/views/${encodeURIComponent(id)}`, { method: "DELETE" }),

  // ── Phase 2: inbox ───────────────────────────────────────────────────
  inboxSummary: (filters?: InboxFilters) => {
    const qs = new URLSearchParams();
    appendFilters(qs, filters);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return jsonFetch<InboxSummary>(`/inbox/summary${suffix}`);
  },
  bulkAction: (body: BulkActionRequest) =>
    jsonFetch<BulkActionResponse>("/inbox/bulk_action", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  inboxExportUrl: (filters?: InboxFilters) => {
    const qs = new URLSearchParams();
    appendFilters(qs, filters);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return `${API_BASE}/inbox/export.csv${suffix}`;
  },
  // Phase 3: Functions and Threat Map
  getFunctions: (params: {
    severity?: string;
    mitre_technique?: string;
    sort?: string;
    page?: number;
    page_size?: number;
  }) =>
    jsonFetch(
      `/functions?${new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      ).toString()}`
    ),
  getFunctionDetail: (functionId: string, window_days?: number) =>
    jsonFetch(`/functions/${functionId}${window_days ? `?window_days=${window_days}` : ""}`),
  getThreatMap: (params: { window?: string }) =>
    jsonFetch(
      `/threat-map?${new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      ).toString()}`
    ),
  getThreatMapGrid: () => jsonFetch("/threat-map/grid"),
  getThreatMapCellDetections: (
    techniqueId: string,
    params?: { window?: string; page?: number; page_size?: number }
  ) =>
    jsonFetch(
      `/threat-map/cells/${techniqueId}/detections?${new URLSearchParams(
        Object.entries(params || {})
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      ).toString()}`
    ),

  // ── Phase 4: system metrics ────────────────────────────────────────────────────────────
  getSystemMetrics: () => jsonFetch<SystemMetricsResponse>("/system/metrics"),
  getSystemMetricsTimeseries: (params: { window?: string; bin?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.window) qs.set("window", params.window);
    if (params.bin) qs.set("bin", params.bin);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return jsonFetch<MetricsTimeseriesResponse>(`/system/metrics/timeseries${suffix}`);
  },
  getDetectors: () => jsonFetch<DetectorPanel>("/system/detectors"),

  // ── Phase 4: settings ──────────────────────────────────────────────────────────────────
  getSettings: () => jsonFetch<SettingsResponse>("/settings"),
  getSettingsRuntime: () => jsonFetch<RuntimeRuntimeConfig>("/settings/runtime"),
  getSettingsPolicy: () => jsonFetch<RedactionPolicy>("/settings/policy"),
  getSettingsGUI: () => jsonFetch<GUIConfigSnapshot>("/settings/gui"),

  // ── Phase 4: audit ────────────────────────────────────────────────────────────────────
  listAudit: (params: {
    actor?: string;
    subject_kind?: string;
    action?: string;
    since?: string;
    until?: string;
    page?: number;
    page_size?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.actor) qs.set("actor", params.actor);
    if (params.subject_kind) qs.set("subject_kind", params.subject_kind);
    if (params.action) qs.set("action", params.action);
    if (params.since) qs.set("since", params.since);
    if (params.until) qs.set("until", params.until);
    if (params.page) qs.set("page", String(params.page));
    if (params.page_size) qs.set("page_size", String(params.page_size));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return jsonFetch<AuditEventListResponse>(`/audit${suffix}`);
  },
  getAuditEvent: (id: string) => jsonFetch<AuditEvent>(`/audit/${encodeURIComponent(id)}`),
  verifyAuditChain: () => jsonFetch<AuditChainVerification>("/audit/verify"),
  auditExportCsvUrl: (params?: {
    actor?: string;
    subject_kind?: string;
    action?: string;
    since?: string;
    until?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.actor) qs.set("actor", params.actor);
    if (params?.subject_kind) qs.set("subject_kind", params.subject_kind);
    if (params?.action) qs.set("action", params.action);
    if (params?.since) qs.set("since", params.since);
    if (params?.until) qs.set("until", params.until);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return `${API_BASE}/audit/export.csv${suffix}`;
  },
  auditExportJsonUrl: (params?: {
    actor?: string;
    subject_kind?: string;
    action?: string;
    since?: string;
    until?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.actor) qs.set("actor", params.actor);
    if (params?.subject_kind) qs.set("subject_kind", params.subject_kind);
    if (params?.action) qs.set("action", params.action);
    if (params?.since) qs.set("since", params.since);
    if (params?.until) qs.set("until", params.until);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return `${API_BASE}/audit/export.json${suffix}`;
  },

  // ── AWS Live Ingest ──────────────────────────────────────────────────────────────────
  awsFunctions: () =>
    jsonFetch<{ functions: AwsFunction[]; region: string; count: number; available: boolean; reason?: string }>("/aws/functions"),
  awsPull: (body: { function_name: string; minutes_back?: number; max_events?: number }) =>
    jsonFetch<{ pulled: number; ingested: number; detections: { id: string; severity: string; function_id: string }[]; errors: string[] }>("/aws/pull", { method: "POST", body: JSON.stringify(body) }),
};

export const queryKeys = {
  health: ["health"] as const,
  systemStatus: ["system", "status"] as const,
  systemMetrics: ["system", "metrics"] as const,
  systemMetricsTimeseries: (params: object = {}) => ["system", "metrics", "timeseries", params] as const,
  detectors: ["system", "detectors"] as const,
  settings: ["settings"] as const,
  settingsRuntime: ["settings", "runtime"] as const,
  settingsPolicy: ["settings", "policy"] as const,
  settingsGUI: ["settings", "gui"] as const,
  audit: (filters: object = {}) => ["audit", filters] as const,
  auditEvent: (id: string) => ["audit", id] as const,
  auditChain: ["audit", "chain"] as const,
  detections: (filters: object = {}) => ["detections", filters] as const,
  detection: (id: string) => ["detection", id] as const,
  summary: ["dashboard", "summary"] as const,
  cases: (filters: object = {}) => ["cases", filters] as const,
  case: (id: string) => ["case", id] as const,
  caseEvents: (id: string) => ["case", id, "events"] as const,
  caseComments: (id: string) => ["case", id, "comments"] as const,
  caseDetections: (id: string) => ["case", id, "detections"] as const,
  views: ["views"] as const,
  inboxSummary: (filters: object = {}) => ["inbox", "summary", filters] as const,
};

/**
 * SSE hook: subscribe to /api/detections/stream and invalidate the
 * detections + summary caches when a new detection arrives.
 *
 * The hook silently no-ops in non-browser environments (tests).
 */
export function useDetectionStream(): void {
  const qc = useQueryClient();
  useEffect(() => {
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      return;
    }
    const source = new EventSource(`${API_BASE}/detections/stream`);
    const handleDetection = (_evt: MessageEvent) => {
      qc.invalidateQueries({ queryKey: ["detections"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["inbox"] });
    };
    source.addEventListener("detection", handleDetection as EventListener);
    return () => {
      source.removeEventListener("detection", handleDetection as EventListener);
      source.close();
    };
  }, [qc]);
}

/**
 * Phase 2 SSE hook: listen for `event: case` and `event: bulk` frames and
 * invalidate the case + inbox caches.  Phase-1 ``useDetectionStream`` keeps
 * working unchanged.
 */
export function useCaseStream(): void {
  const qc = useQueryClient();
  useEffect(() => {
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      return;
    }
    const source = new EventSource(`${API_BASE}/detections/stream`);
    const onCase = (_evt: MessageEvent) => {
      qc.invalidateQueries({ queryKey: ["cases"] });
      qc.invalidateQueries({ queryKey: ["case"] });
      qc.invalidateQueries({ queryKey: ["inbox"] });
      qc.invalidateQueries({ queryKey: ["detections"] });
    };
    const onBulk = (_evt: MessageEvent) => {
      qc.invalidateQueries({ queryKey: ["detections"] });
      qc.invalidateQueries({ queryKey: ["cases"] });
      qc.invalidateQueries({ queryKey: ["inbox"] });
    };
    source.addEventListener("case", onCase as EventListener);
    source.addEventListener("bulk", onBulk as EventListener);
    return () => {
      source.removeEventListener("case", onCase as EventListener);
      source.removeEventListener("bulk", onBulk as EventListener);
      source.close();
    };
  }, [qc]);
}

export function appendStreamRow(
  current: DetectionListResponse | undefined,
  row: DetectionSummary
): DetectionListResponse {
  if (!current) {
    return { items: [row], total: 1, page: 1, page_size: 50 };
  }
  return {
    ...current,
    items: [row, ...current.items].slice(0, current.page_size),
    total: current.total + 1,
  };
}

export type { CaseSummary };
