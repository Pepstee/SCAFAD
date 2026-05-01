import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";

import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Empty } from "@/components/ui/Empty";
import { Badge } from "@/components/ui/Badge";
import { SeverityChip } from "@/components/ui/SeverityChip";

import { BulkToolbar } from "@/components/inbox/BulkToolbar";
import { FilterBar } from "@/components/inbox/FilterBar";
import { InboxTable } from "@/components/inbox/InboxTable";
import { SavedViews } from "@/components/inbox/SavedViews";
import { CaseDrawer } from "@/components/cases/CaseDrawer";

import { api, queryKeys, useCaseStream, useDetectionStream } from "@/lib/api";
import { useTableKeyboardNav } from "@/lib/keyboard";
import { clsx, formatTimestamp } from "@/lib/format";
import type {
  BulkActionType,
  CaseStatus,
  CaseSummary,
  DetectionSummary,
  DetectionDetail,
  InboxFilters,
  Severity,
} from "@/lib/types";

const PAGE_SIZE = 50;

function parseListParam(raw: string | null): string[] | undefined {
  if (!raw) return undefined;
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function filtersFromSearchParams(params: URLSearchParams): InboxFilters {
  return {
    severity: parseListParam(params.get("severity")) as Severity[] | undefined,
    anomaly_type: parseListParam(params.get("anomaly_type")),
    mitre_technique: parseListParam(params.get("mitre_technique")),
    function_id: params.get("function_id") || undefined,
    decision: parseListParam(params.get("decision")),
    risk_band: parseListParam(params.get("risk_band")),
    text: params.get("text") || undefined,
    since: params.get("since") || undefined,
    until: params.get("until") || undefined,
    case_status: (params.get("case_status") as CaseStatus | "none" | null) || undefined,
  };
}

function filtersToSearchParams(filters: InboxFilters): URLSearchParams {
  const out = new URLSearchParams();
  if (filters.severity?.length) out.set("severity", filters.severity.join(","));
  if (filters.anomaly_type?.length) out.set("anomaly_type", filters.anomaly_type.join(","));
  if (filters.mitre_technique?.length)
    out.set("mitre_technique", filters.mitre_technique.join(","));
  if (filters.function_id) out.set("function_id", filters.function_id);
  if (filters.decision?.length) out.set("decision", filters.decision.join(","));
  if (filters.risk_band?.length) out.set("risk_band", filters.risk_band.join(","));
  if (filters.text) out.set("text", filters.text);
  if (filters.since) out.set("since", filters.since);
  if (filters.until) out.set("until", filters.until);
  if (filters.case_status) out.set("case_status", filters.case_status);
  return out;
}

export default function InboxPage() {
  useDetectionStream();
  useCaseStream();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => filtersFromSearchParams(searchParams), [searchParams]);

  // Extract selected detection ID from URL
  const selectedDetectionId = searchParams.get("selected") ?? null;

  const updateFilters = useCallback(
    (next: InboxFilters) => {
      setSearchParams(filtersToSearchParams(next));
    },
    [setSearchParams]
  );

  const updateSelectedDetection = useCallback(
    (id: string | null) => {
      const params = new URLSearchParams(searchParams);
      if (id) {
        params.set("selected", id);
      } else {
        params.delete("selected");
      }
      setSearchParams(params);
    },
    [searchParams, setSearchParams]
  );

  const resetFilters = useCallback(() => updateFilters({}), [updateFilters]);

  const detectionsQuery = useQuery({
    queryKey: queryKeys.detections({ kind: "inbox", ...filters }),
    queryFn: () => api.listInboxDetections({ filters, page_size: PAGE_SIZE }),
    refetchInterval: 30_000,
  });
  const summaryQuery = useQuery({
    queryKey: queryKeys.inboxSummary(filters),
    queryFn: () => api.inboxSummary(filters),
    refetchInterval: 30_000,
  });
  const casesQuery = useQuery({
    queryKey: queryKeys.cases({ status: "open" }),
    queryFn: () => api.listCases({ page_size: 50 }),
  });

  // Load full detail for selected detection (preview panel)
  const detailQuery = useQuery({
    queryKey: queryKeys.detection(selectedDetectionId ?? ""),
    queryFn: () => api.getDetection(selectedDetectionId!),
    enabled: !!selectedDetectionId,
    staleTime: 30_000,
  });

  const items: DetectionSummary[] = detectionsQuery.data?.items ?? [];
  const total = detectionsQuery.data?.total ?? 0;

  const knownAnomalyTypes = useMemo(() => {
    const set = new Set<string>();
    items.forEach((row) => set.add(row.anomaly_type));
    return Array.from(set).sort();
  }, [items]);
  const knownTechniques = useMemo(() => {
    const set = new Set<string>();
    items.forEach((row) => row.mitre_techniques.forEach((t) => set.add(t)));
    return Array.from(set).sort();
  }, [items]);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [drawerCaseId, setDrawerCaseId] = useState<string | null>(null);
  const [dividerX, setDividerX] = useState(45); // Split pane left width percentage
  const [showKeyboardLegend, setShowKeyboardLegend] = useState(false);
  const dividerRef = useRef<HTMLDivElement>(null);

  // Reset selection when filters change.
  useEffect(() => {
    setSelected(new Set());
    setFocusedIndex(0);
  }, [searchParams]);

  // Build a quick lookup of detection -> linked case via the detection summaries.
  const caseByDetection = useMemo(() => {
    const out: Record<string, CaseSummary | undefined> = {};
    return out;
  }, []);

  const toggleSelected = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    setSelected((prev) => {
      if (prev.size === items.length) return new Set();
      return new Set(items.map((r) => r.id));
    });
  }, [items]);

  const openDetail = useCallback(
    (row: DetectionSummary) => navigate(`/detections/${encodeURIComponent(row.id)}`),
    [navigate]
  );
  const openCase = useCallback((caseSummary: CaseSummary) => {
    setDrawerCaseId(caseSummary.id);
  }, []);

  const bulkMut = useMutation({
    mutationFn: (variables: { action: BulkActionType; payload?: Record<string, unknown> }) =>
      api.bulkAction({
        action: variables.action,
        detection_ids: Array.from(selected),
        payload: variables.payload ?? {},
      }),
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ["detections"] });
      qc.invalidateQueries({ queryKey: ["cases"] });
      qc.invalidateQueries({ queryKey: ["inbox"] });
      if (response.case_id) setDrawerCaseId(response.case_id);
      setSelected(new Set());
    },
  });

  // Enhanced keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in input
      if (["INPUT", "TEXTAREA"].includes((e.target as HTMLElement).tagName)) {
        return;
      }

      switch (e.key.toLowerCase()) {
        case "j":
          // Move selection down
          e.preventDefault();
          setFocusedIndex((prev) => Math.min(prev + 1, items.length - 1));
          break;
        case "k":
          // Move selection up
          e.preventDefault();
          setFocusedIndex((prev) => Math.max(prev - 1, 0));
          break;
        case "enter":
          // Open full detail page
          if (items[focusedIndex]) {
            e.preventDefault();
            openDetail(items[focusedIndex]);
          }
          break;
        case " ":
          // Toggle checkbox
          if (items[focusedIndex]) {
            e.preventDefault();
            toggleSelected(items[focusedIndex].id);
          }
          break;
        case "e":
          // Open case from selection
          if (selected.size > 0) {
            e.preventDefault();
            const title = window.prompt("Case title", "New investigation") || "";
            if (title) {
              bulkMut.mutate({ action: "open_case", payload: { title } });
            }
          }
          break;
        case "f":
          // Mark false positive (dismiss)
          if (selected.size > 0) {
            e.preventDefault();
            bulkMut.mutate({ action: "dismiss", payload: { reason: "false positive" } });
          }
          break;
        case "escape":
          // Clear selection and preview
          e.preventDefault();
          setSelected(new Set());
          updateSelectedDetection(null);
          break;
        case "?":
          // Show keyboard legend
          e.preventDefault();
          setShowKeyboardLegend((prev) => !prev);
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [items, focusedIndex, selected, openDetail, toggleSelected, updateSelectedDetection, bulkMut]);

  // Resizable divider
  useEffect(() => {
    const handleMouseDown = () => {
      const handleMouseMove = (e: MouseEvent) => {
        if (dividerRef.current?.parentElement) {
          const container = dividerRef.current.parentElement;
          const rect = container.getBoundingClientRect();
          const newX = ((e.clientX - rect.left) / rect.width) * 100;
          if (newX > 30 && newX < 70) {
            setDividerX(newX);
          }
        }
      };

      const handleMouseUp = () => {
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
      };

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    };

    const divider = dividerRef.current;
    if (divider) {
      divider.addEventListener("mousedown", handleMouseDown);
    }

    return () => {
      if (divider) {
        divider.removeEventListener("mousedown", handleMouseDown);
      }
    };
  }, []);

  return (
    <div className="flex h-full flex-col gap-4">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Detection Inbox</h1>
          <p className="mt-1 text-sm text-surface-muted">
            Filterable triage queue · {total.toLocaleString()} detections in scope
            {selectedDetectionId && ` · Preview: ${selectedDetectionId.slice(0, 8)}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowKeyboardLegend((prev) => !prev)}
            className="rounded border border-surface-border px-2 py-1 text-[11px] uppercase tracking-wide text-ink-dim hover:bg-surface-subtle"
            title="Press ? for shortcuts"
          >
            ⌨ Help
          </button>
          <SavedViews
            filters={filters}
            onApply={(view) => updateFilters(view.filter_json as InboxFilters)}
          />
        </div>
      </header>

      {showKeyboardLegend && <KeyboardLegend />}

      {summaryQuery.data && (
        <section
          aria-label="Inbox aggregates"
          className="grid grid-cols-2 gap-3 md:grid-cols-4"
        >
          <SummaryTile label="Observe" value={summaryQuery.data.severity_counts.observe} />
          <SummaryTile label="Review" value={summaryQuery.data.severity_counts.review} />
          <SummaryTile label="Escalate" value={summaryQuery.data.severity_counts.escalate} />
          <SummaryTile
            label="Open cases linked"
            value={summaryQuery.data.case_status_counts.open}
          />
        </section>
      )}

      <Card className="flex flex-1 flex-col overflow-hidden p-0">
        <FilterBar
          filters={filters}
          onChange={updateFilters}
          onReset={resetFilters}
          knownAnomalyTypes={knownAnomalyTypes}
          knownTechniques={knownTechniques}
        />
        <BulkToolbar
          selectedCount={selected.size}
          onAction={(action, payload) => bulkMut.mutate({ action, payload })}
          onClearSelection={() => setSelected(new Set())}
          exportHref={api.inboxExportUrl(filters)}
          cases={casesQuery.data?.items ?? []}
        />

        {/* Split-pane layout: Detection list (left) + Preview panel (right) */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left pane: Detection list */}
          <div style={{ width: `${dividerX}%` }} className="overflow-hidden flex flex-col">
            {detectionsQuery.isLoading ? (
              <div className="p-6">
                <Skeleton className="h-40 w-full" />
              </div>
            ) : items.length === 0 ? (
              <Empty
                title="No detections match"
                body="Widen your filters or wait for new detections to arrive."
              />
            ) : (
              <InboxTable
                rows={items}
                caseByDetection={caseByDetection}
                selected={selected}
                onToggleSelected={(id) => {
                  toggleSelected(id);
                  updateSelectedDetection(id);
                }}
                onToggleAll={toggleAll}
                focusedIndex={focusedIndex}
                setFocusedIndex={(idx) => {
                  setFocusedIndex(idx);
                  // Auto-load preview for focused row
                  if (items[idx]) {
                    updateSelectedDetection(items[idx].id);
                  }
                }}
                onOpenDetail={openDetail}
                onOpenCase={openCase}
              />
            )}
          </div>

          {/* Draggable divider */}
          <div
            ref={dividerRef}
            className="w-1 cursor-col-resize bg-surface-border hover:bg-ink-accent transition-colors"
            title="Drag to resize"
          />

          {/* Right pane: Preview panel */}
          <div style={{ width: `${100 - dividerX}%` }} className="overflow-hidden flex flex-col border-l border-surface-border bg-surface-subtle">
            {selectedDetectionId && detailQuery.data ? (
              <DetectionPreview
                detection={detailQuery.data}
                onClose={() => updateSelectedDetection(null)}
                onMarkFP={() => {
                  bulkMut.mutate({ action: "dismiss", payload: { reason: "false positive" } });
                  updateSelectedDetection(null);
                }}
                onCreateCase={() => {
                  if (selectedDetectionId) {
                    const title = window.prompt("Case title", "New investigation") || "";
                    if (title) {
                      bulkMut.mutate({ action: "open_case", payload: { title } });
                      updateSelectedDetection(null);
                    }
                  }
                }}
              />
            ) : selectedDetectionId && detailQuery.isLoading ? (
              <div className="flex items-center justify-center h-full">
                <Skeleton className="h-40 w-full m-4" />
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-center text-surface-muted">
                <div>
                  <p className="text-sm">Select a detection to preview</p>
                  <p className="text-[11px] mt-1 text-surface-muted">Click a row or press ↵ to open</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </Card>

      <CaseDrawer
        caseId={drawerCaseId}
        open={Boolean(drawerCaseId)}
        onClose={() => setDrawerCaseId(null)}
      />
    </div>
  );
}

function SummaryTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-surface-border bg-surface-panel px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-surface-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums text-ink">
        {value.toLocaleString()}
      </div>
    </div>
  );
}

/**
 * Detection Preview Panel — right-pane summary of a selected detection.
 * Shows header, anomaly score visualization, MITRE techniques, and quick action buttons.
 */
interface DetectionPreviewProps {
  detection: DetectionDetail;
  onClose: () => void;
  onMarkFP: () => void;
  onCreateCase: () => void;
}

function DetectionPreview({
  detection,
  onClose,
  onMarkFP,
  onCreateCase,
}: DetectionPreviewProps) {
  const trustScore = detection.trust_score;
  const anomalyScore = Math.min(trustScore, 1.0); // Clamp for visualization

  return (
    <div className="flex flex-col overflow-y-auto h-full">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-surface-border bg-surface-panel px-4 py-3">
        <div className="flex items-center gap-2">
          <SeverityChip severity={detection.severity} compact />
          <div className="flex flex-col">
            <span className="text-xs font-mono text-ink truncate">{detection.function_id}</span>
            <span className="text-[10px] text-surface-muted">
              {formatTimestamp(detection.ingested_at)}
            </span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 hover:bg-surface-border"
          title="Close preview (Esc)"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {/* Detection ID */}
        <div className="text-[10px]">
          <div className="uppercase tracking-wider text-surface-muted mb-1">Detection ID</div>
          <code className="block text-xs font-mono text-ink-dim break-all bg-surface-panel rounded p-2 border border-surface-border">
            {detection.id}
          </code>
        </div>

        {/* Anomaly score gauge */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] uppercase tracking-wider text-surface-muted">
              Anomaly Score
            </span>
            <span className="text-sm font-semibold text-ink">{trustScore.toFixed(3)}</span>
          </div>
          <div className="h-2 bg-surface-panel rounded-full overflow-hidden border border-surface-border">
            <div
              className="h-full bg-gradient-to-r from-blue-500 via-yellow-500 to-red-500"
              style={{ width: `${anomalyScore * 100}%` }}
            />
          </div>
        </div>

        {/* Anomaly type */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-surface-muted mb-1">
            Anomaly Type
          </div>
          <Badge tone="info" size="sm">
            {detection.anomaly_type}
          </Badge>
        </div>

        {/* MITRE Techniques */}
        {detection.mitre_techniques.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-surface-muted mb-2">
              MITRE ATT&CK
            </div>
            <div className="flex flex-wrap gap-2">
              {detection.mitre_techniques.map((technique) => (
                <Badge key={technique} tone="warn" size="sm">
                  {technique}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Risk band and decision */}
        <div className="grid grid-cols-2 gap-2">
          {detection.risk_band && (
            <div className="text-[10px]">
              <div className="uppercase tracking-wider text-surface-muted mb-1">Risk Band</div>
              <span className="text-xs font-mono text-ink-dim">{detection.risk_band}</span>
            </div>
          )}
          {detection.decision && (
            <div className="text-[10px]">
              <div className="uppercase tracking-wider text-surface-muted mb-1">Decision</div>
              <span className="text-xs font-mono text-ink-dim">{detection.decision}</span>
            </div>
          )}
        </div>

        {/* Event ID */}
        <div className="text-[10px]">
          <div className="uppercase tracking-wider text-surface-muted mb-1">Event ID</div>
          <code className="text-xs font-mono text-ink-dim break-all">{detection.event_id}</code>
        </div>
      </div>

      {/* Quick action buttons */}
      <div className="border-t border-surface-border bg-surface-panel px-4 py-3 flex gap-2">
        <button
          onClick={onCreateCase}
          className="flex-1 rounded border border-surface-border bg-surface-subtle px-2 py-1.5 text-[11px] uppercase tracking-wide text-ink-dim hover:bg-surface-border transition-colors"
          title="Press E to create a case"
        >
          Open Case
        </button>
        <button
          onClick={onMarkFP}
          className="flex-1 rounded border border-surface-border bg-surface-subtle px-2 py-1.5 text-[11px] uppercase tracking-wide text-ink-dim hover:bg-surface-border transition-colors"
          title="Press F to mark false positive"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

/**
 * Keyboard Legend — shows available shortcuts.
 */
function KeyboardLegend() {
  const shortcuts = [
    { key: "j / k", description: "Move selection up/down" },
    { key: "Enter", description: "Open full detection detail" },
    { key: "Space", description: "Toggle selection checkbox" },
    { key: "E", description: "Open case from selection" },
    { key: "F", description: "Dismiss as false positive" },
    { key: "Escape", description: "Clear selection and preview" },
    { key: "?", description: "Toggle this legend" },
  ];

  return (
    <div className="rounded border border-surface-border bg-surface-panel px-4 py-3">
      <div className="text-xs">
        <p className="font-semibold text-ink mb-2">Keyboard Shortcuts</p>
        <div className="grid grid-cols-1 gap-2 text-[11px] text-surface-muted md:grid-cols-2">
          {shortcuts.map((s) => (
            <div key={s.key} className="flex gap-3">
              <span className="min-w-20 font-mono font-semibold text-ink">{s.key}</span>
              <span>{s.description}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
