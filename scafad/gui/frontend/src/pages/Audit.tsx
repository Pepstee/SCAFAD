import React, { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "@/lib/api";
import type { AuditEvent, AuditFilterOptions } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DataTable, type ColumnDef } from "@/components/ui/DataTable";
import { Skeleton } from "@/components/ui/Skeleton";
import { Empty } from "@/components/ui/Empty";

/**
 * Premium real-time forensic audit trail.
 * Features:
 * - Chain integrity verification with visual indicator
 * - Dual-view toggle: Table vs Timeline
 * - Smart filtering by actor, subject kind, action
 * - Real-time polling with flash highlights on new events
 * - Exportable as CSV/JSON
 * - Paginated with configurable page size
 */
export default function AuditPage() {
  const [viewType, setViewType] = useState<"table" | "timeline">("table");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [actor, setActor] = useState("");
  const [subjectKind, setSubjectKind] = useState("");
  const [action, setAction] = useState("");
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);
  const [flashingIds, setFlashingIds] = useState<Set<string>>(new Set());
  const [newEventCount, setNewEventCount] = useState(0);
  const previousDataRef = useRef<string[]>([]);

  // Main audit data query
  const audit = useQuery({
    queryKey: queryKeys.audit({
      actor: actor || undefined,
      subject_kind: subjectKind || undefined,
      action: action || undefined,
      page,
      page_size: pageSize,
    }),
    queryFn: () =>
      api.listAudit({
        actor: actor || undefined,
        subject_kind: subjectKind || undefined,
        action: action || undefined,
        page,
        page_size: pageSize,
      }),
    refetchInterval: 5_000,
  });

  // Chain verification query
  const chain = useQuery({
    queryKey: queryKeys.auditChain,
    queryFn: () => api.verifyAuditChain(),
    refetchInterval: 60_000,
  });

  // Detect new events and highlight them
  useEffect(() => {
    if (!audit.data?.items) return;

    const currentIds = audit.data.items.map((item) => item.id);
    const newIds = currentIds.filter((id) => !previousDataRef.current.includes(id));

    if (newIds.length > 0) {
      setNewEventCount((prev) => prev + newIds.length);
      setFlashingIds(new Set(newIds));

      // Flash for 1.5s
      const timer = setTimeout(() => {
        setFlashingIds(new Set());
      }, 1500);

      return () => clearTimeout(timer);
    }

    previousDataRef.current = currentIds;
  }, [audit.data?.items]);

  const data = audit.data;
  const chainData = chain.data;
  const pageCount = data ? Math.ceil(data.total / (data.page_size || pageSize)) : 1;

  // Filter options for dropdowns
  const actorOptions = useMemo<string[]>(() => {
    if (!data?.items) return [];
    return Array.from(new Set(data.items.map((e) => e.actor_id))).sort();
  }, [data?.items]);

  const subjectKindOptions = useMemo<string[]>(() => {
    if (!data?.items) return [];
    return Array.from(new Set(data.items.map((e) => e.subject_kind))).sort();
  }, [data?.items]);

  const actionOptions = useMemo<string[]>(() => {
    if (!data?.items) return [];
    return Array.from(new Set(data.items.map((e) => e.action))).sort();
  }, [data?.items]);

  // Event handlers
  const handleFilterChange = () => {
    setPage(1);
    setNewEventCount(0);
  };

  const handleActorChange = (val: string) => {
    setActor(val);
    handleFilterChange();
  };

  const handleSubjectKindChange = (val: string) => {
    setSubjectKind(val);
    handleFilterChange();
  };

  const handleActionChange = (val: string) => {
    setAction(val);
    handleFilterChange();
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    setPage(1);
  };

  const handleClearFilters = () => {
    setActor("");
    setSubjectKind("");
    setAction("");
    setPage(1);
  };

  const hasActiveFilters = actor || subjectKind || action;

  // Column definitions for table view
  const columns: ColumnDef<AuditEvent>[] = [
    {
      key: "ts",
      header: "Time",
      width: "140px",
      render: (row) => <span className="text-xs text-surface-muted">{formatRelativeTime(row.ts)}</span>,
    },
    {
      key: "actor_id",
      header: "Actor",
      width: "100px",
      render: (row) => <span className="font-mono text-xs">{row.actor_id}</span>,
    },
    {
      key: "action",
      header: "Action",
      width: "120px",
      render: (row) => (
        <Badge tone={getActionTone(row.action)} className="capitalize">
          {row.action}
        </Badge>
      ),
    },
    {
      key: "subject",
      header: "Subject",
      width: "150px",
      render: (row) => (
        <div className="flex items-center gap-1">
          <Badge tone="info" className="capitalize">
            {row.subject_kind}
          </Badge>
          {row.subject_id && <span className="font-mono text-xs text-surface-muted truncate max-w-[80px]">{row.subject_id.substring(0, 12)}</span>}
        </div>
      ),
    },
    {
      key: "row_hash",
      header: "Hash",
      width: "120px",
      render: (row) => (
        <span className="font-mono text-xs text-surface-muted" title={row.row_hash}>
          {row.row_hash.substring(0, 8)}...
        </span>
      ),
    },
  ];

  if (audit.isLoading && !data) {
    return (
      <div className="flex flex-col gap-6 p-6">
        <h1 className="text-2xl font-bold">Audit Trail</h1>
        <Card>
          <div className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Audit Trail</h1>
        <div className="flex gap-2">
          <a
            href={api.auditExportCsvUrl({
              actor: actor || undefined,
              subject_kind: subjectKind || undefined,
              action: action || undefined,
            })}
            download
            className="px-3 py-1.5 rounded text-sm font-medium bg-surface-panel border border-surface-border text-ink-accent hover:bg-surface-subtle transition-colors"
          >
            ↓ Export CSV
          </a>
          <a
            href={api.auditExportJsonUrl({
              actor: actor || undefined,
              subject_kind: subjectKind || undefined,
              action: action || undefined,
            })}
            download
            className="px-3 py-1.5 rounded text-sm font-medium bg-surface-panel border border-surface-border text-ink-accent hover:bg-surface-subtle transition-colors"
          >
            ↓ Export JSON
          </a>
        </div>
      </div>

      {/* Chain Integrity Banner */}
      {chainData && (
        <div
          className={`rounded-lg border p-4 backdrop-blur-sm transition-all ${
            chainData.ok
              ? "border-green-500/40 bg-green-950/20 shadow-[0_0_20px_rgba(34,197,94,0.15)]"
              : "border-red-500/40 bg-red-950/20 shadow-[0_0_20px_rgba(255,77,77,0.15)]"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full font-semibold text-sm ${
                  chainData.ok
                    ? "bg-green-950/40 text-green-300 border border-green-500/30"
                    : "bg-red-950/40 text-red-300 border border-red-500/30"
                }`}
              >
                <span>{chainData.ok ? "✓" : "✗"}</span>
                <span>Chain {chainData.ok ? "Verified" : "Broken"}</span>
              </div>
              <div className="text-xs text-surface-muted space-y-0.5">
                <div>{chainData.total_rows.toLocaleString()} rows verified</div>
                {chainData.last_verified_id && (
                  <div className="font-mono text-xs">
                    Last: <span className="text-ink-dim">{chainData.last_verified_id.substring(0, 12)}...</span>
                  </div>
                )}
                {chainData.broken_at && (
                  <div className="text-red-300">
                    Broken at: <span className="font-mono">{chainData.broken_at.substring(0, 12)}...</span>
                  </div>
                )}
              </div>
            </div>
            {newEventCount > 0 && (
              <Badge tone="success" className="animate-pulse">
                {newEventCount} new events
              </Badge>
            )}
          </div>
        </div>
      )}

      {/* View Type Toggle */}
      <div className="flex items-center gap-4">
        <div className="inline-flex rounded-full bg-surface-panel border border-surface-border p-1">
          <button
            onClick={() => setViewType("table")}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              viewType === "table"
                ? "bg-ink-accent text-surface-base"
                : "text-ink-dim hover:text-ink-default"
            }`}
          >
            Table
          </button>
          <button
            onClick={() => setViewType("timeline")}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              viewType === "timeline"
                ? "bg-ink-accent text-surface-base"
                : "text-ink-dim hover:text-ink-default"
            }`}
          >
            Timeline
          </button>
        </div>

        {hasActiveFilters && (
          <button
            onClick={handleClearFilters}
            className="px-3 py-1.5 rounded text-xs font-medium text-surface-muted hover:text-ink-default border border-surface-border hover:border-surface-subtle transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Smart Filter Bar */}
      <Card description="Filter by actor, subject kind, or action">
        <div className="flex flex-wrap gap-3">
          <FilterDropdown
            label="Actor"
            value={actor}
            onChange={handleActorChange}
            options={actorOptions}
            placeholder="All actors"
          />
          <FilterDropdown
            label="Subject Kind"
            value={subjectKind}
            onChange={handleSubjectKindChange}
            options={subjectKindOptions}
            placeholder="All subjects"
          />
          <FilterDropdown
            label="Action"
            value={action}
            onChange={handleActionChange}
            options={actionOptions}
            placeholder="All actions"
          />
        </div>
      </Card>

      {/* Main Content Area */}
      {data && data.items.length === 0 ? (
        <Empty
          title="No audit events found"
          body={hasActiveFilters ? "Try adjusting your filters" : "Audit events will appear here"}
        />
      ) : data ? (
        <>
          {/* Table View */}
          {viewType === "table" && (
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-surface-border">
                    <tr>
                      <th className="px-3 py-2 text-left font-semibold text-xs uppercase tracking-wide text-surface-muted">Time</th>
                      <th className="px-3 py-2 text-left font-semibold text-xs uppercase tracking-wide text-surface-muted">Actor</th>
                      <th className="px-3 py-2 text-left font-semibold text-xs uppercase tracking-wide text-surface-muted">Action</th>
                      <th className="px-3 py-2 text-left font-semibold text-xs uppercase tracking-wide text-surface-muted">Subject</th>
                      <th className="px-3 py-2 text-left font-semibold text-xs uppercase tracking-wide text-surface-muted">Hash</th>
                      <th className="w-8"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border/60">
                    {data.items.map((event) => (
                      <React.Fragment key={event.id}>
                        <tr
                          className={`transition-all ${
                            flashingIds.has(event.id)
                              ? "bg-cyan-950/40 border-l-2 border-l-cyan-400"
                              : "hover:bg-surface-subtle"
                          }`}
                        >
                          <td className="px-3 py-2 text-xs text-surface-muted">{formatRelativeTime(event.ts)}</td>
                          <td className="px-3 py-2 font-mono text-xs text-ink">{event.actor_id}</td>
                          <td className="px-3 py-2">
                            <Badge tone={getActionTone(event.action)} className="capitalize">
                              {event.action}
                            </Badge>
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-1">
                              <Badge tone="info" className="capitalize">
                                {event.subject_kind}
                              </Badge>
                              {event.subject_id && (
                                <span className="font-mono text-xs text-surface-muted truncate max-w-[80px]">
                                  {event.subject_id.substring(0, 12)}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-2 font-mono text-xs text-surface-muted" title={event.row_hash}>
                            {event.row_hash.substring(0, 8)}...
                          </td>
                          <td className="px-3 py-2 text-center">
                            <button
                              onClick={() =>
                                setExpandedRowId(expandedRowId === event.id ? null : event.id)
                              }
                              className="inline-flex items-center justify-center w-6 h-6 rounded hover:bg-surface-subtle transition-colors"
                            >
                              <span className="text-xs text-ink-dim">
                                {expandedRowId === event.id ? "−" : "+"}
                              </span>
                            </button>
                          </td>
                        </tr>
                        {expandedRowId === event.id && (
                          <tr className="bg-surface-subtle/50 border-b border-surface-border">
                            <td colSpan={6} className="px-3 py-4">
                              <EventDetails event={event} />
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Timeline View */}
          {viewType === "timeline" && (
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-6 top-0 bottom-0 w-px bg-gradient-to-b from-surface-border via-surface-border to-transparent"></div>

              {/* Timeline events */}
              <div className="space-y-4">
                {data.items.map((event, index) => (
                  <div
                    key={event.id}
                    className={`relative pl-20 transition-all ${
                      flashingIds.has(event.id) ? "bg-cyan-950/20 rounded p-3 border border-cyan-400/30" : "p-2"
                    }`}
                  >
                    {/* Timeline node */}
                    <div
                      className={`absolute left-0 top-2 w-14 h-14 rounded-full border-2 flex items-center justify-center text-xs font-semibold ${
                        getActionNodeStyle(event.action)
                      }`}
                    >
                      {getActionIcon(event.action)}
                    </div>

                    {/* Event content card */}
                    <Card className="ml-2">
                      <div className="space-y-2">
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="text-sm font-semibold text-ink capitalize">{event.action}</div>
                            <div className="text-xs text-surface-muted mt-1">
                              <span className="inline-block px-2 py-0.5 rounded bg-surface-subtle mr-2">
                                {event.actor_id}
                              </span>
                              <span className="inline-block px-2 py-0.5 rounded bg-surface-subtle">
                                {formatRelativeTime(event.ts)}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <Badge tone="info" className="capitalize">
                            {event.subject_kind}
                          </Badge>
                          {event.subject_id && (
                            <span className="font-mono text-xs text-surface-muted bg-surface-subtle px-2 py-1 rounded">
                              {event.subject_id}
                            </span>
                          )}
                        </div>

                        {Object.keys(event.payload).length > 0 && (
                          <details className="text-xs">
                            <summary className="cursor-pointer text-ink-dim hover:text-ink-default">
                              Show metadata
                            </summary>
                            <pre className="mt-2 p-2 bg-surface-subtle rounded text-xs overflow-auto max-h-40">
                              {JSON.stringify(event.payload, null, 2)}
                            </pre>
                          </details>
                        )}

                        <div className="text-xs font-mono text-surface-muted pt-2 border-t border-surface-border">
                          <div>Hash: {event.row_hash}</div>
                          {event.prev_hash && <div>Prev: {event.prev_hash}</div>}
                        </div>
                      </div>
                    </Card>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Pagination Controls */}
          <Card description="Navigate results and adjust page size">
            <div className="flex items-center justify-between gap-4">
              <div className="text-sm text-surface-muted">
                Showing {(page - 1) * pageSize + 1}–
                {Math.min(page * pageSize, data.total)} of {data.total.toLocaleString()}
              </div>

              <div className="flex items-center gap-4">
                {/* Page size selector */}
                <div className="flex items-center gap-2">
                  <label className="text-xs font-medium text-surface-muted">Per page:</label>
                  <select
                    value={pageSize}
                    onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                    className="px-2 py-1 rounded text-sm bg-surface-panel border border-surface-border text-ink hover:bg-surface-subtle transition-colors"
                  >
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                </div>

                {/* Pagination buttons */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page === 1}
                    className="px-3 py-1 rounded text-sm bg-surface-panel border border-surface-border text-ink-dim hover:bg-surface-subtle disabled:opacity-30 transition-colors"
                  >
                    ← Prev
                  </button>

                  <div className="flex items-center gap-1">
                    {Array.from({ length: Math.min(5, pageCount) }).map((_, i) => {
                      const p = i + 1;
                      return (
                        <button
                          key={p}
                          onClick={() => setPage(p)}
                          className={`px-2 py-1 rounded text-sm font-medium transition-colors ${
                            p === page
                              ? "bg-ink-accent text-surface-base"
                              : "bg-surface-panel border border-surface-border text-ink hover:bg-surface-subtle"
                          }`}
                        >
                          {p}
                        </button>
                      );
                    })}
                  </div>

                  <button
                    onClick={() => setPage(Math.min(pageCount, page + 1))}
                    disabled={page === pageCount}
                    className="px-3 py-1 rounded text-sm bg-surface-panel border border-surface-border text-ink-dim hover:bg-surface-subtle disabled:opacity-30 transition-colors"
                  >
                    Next →
                  </button>
                </div>
              </div>
            </div>
          </Card>
        </>
      ) : null}

      {/* Error state */}
      {audit.isError && (
        <Card className="bg-red-950/20 border-red-500/30">
          <div className="text-sm text-red-300">
            Error loading audit trail. Please try refreshing.
          </div>
        </Card>
      )}
    </div>
  );
}

/**
 * Filter dropdown component for smart filtering
 */
function FilterDropdown({
  label,
  value,
  onChange,
  options,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (val: string) => void;
  options: string[];
  placeholder: string;
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
          value
            ? "bg-ink-accent/20 text-ink-accent border border-ink-accent/40"
            : "bg-surface-subtle text-ink-dim border border-surface-border hover:border-surface-muted"
        }`}
      >
        <span className="flex items-center gap-2">
          {value ? `${label}: ${value}` : label}
          <span className="text-xs">▼</span>
        </span>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-48 rounded-lg bg-surface-panel border border-surface-border shadow-lg z-10">
          <div className="p-2">
            <button
              onClick={() => {
                onChange("");
                setIsOpen(false);
              }}
              className="w-full text-left px-3 py-2 rounded text-sm text-ink-dim hover:bg-surface-subtle hover:text-ink transition-colors"
            >
              All {label.toLowerCase()}s
            </button>

            {options.map((opt) => (
              <button
                key={opt}
                onClick={() => {
                  onChange(opt);
                  setIsOpen(false);
                }}
                className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                  value === opt
                    ? "bg-ink-accent/20 text-ink-accent"
                    : "text-ink-dim hover:bg-surface-subtle hover:text-ink"
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Event details panel shown when row is expanded
 */
function EventDetails({ event }: { event: AuditEvent }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs font-semibold text-surface-muted uppercase tracking-wide">ID</div>
          <div className="font-mono text-xs text-ink mt-1 break-all">{event.id}</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-surface-muted uppercase tracking-wide">Timestamp</div>
          <div className="font-mono text-xs text-ink mt-1">{new Date(event.ts).toISOString()}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs font-semibold text-surface-muted uppercase tracking-wide">Row Hash</div>
          <div className="font-mono text-xs text-ink-dim mt-1 break-all truncate" title={event.row_hash}>
            {event.row_hash}
          </div>
        </div>
        <div>
          <div className="text-xs font-semibold text-surface-muted uppercase tracking-wide">Previous Hash</div>
          <div className="font-mono text-xs text-ink-dim mt-1 break-all truncate" title={event.prev_hash}>
            {event.prev_hash}
          </div>
        </div>
      </div>

      {Object.keys(event.payload).length > 0 && (
        <div>
          <div className="text-xs font-semibold text-surface-muted uppercase tracking-wide mb-2">Metadata</div>
          <pre className="p-3 bg-surface-subtle rounded text-xs overflow-auto max-h-60 text-ink-dim font-mono">
            {JSON.stringify(event.payload, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

/**
 * Get badge tone based on action type
 */
function getActionTone(
  action: string
): "neutral" | "info" | "warn" | "danger" | "success" {
  if (action.includes("create") || action.includes("add")) return "success";
  if (action.includes("update") || action.includes("modify")) return "warn";
  if (action.includes("delete") || action.includes("remove")) return "danger";
  if (action.includes("verify")) return "info";
  return "neutral";
}

/**
 * Get timeline node styling based on action
 */
function getActionNodeStyle(action: string): string {
  if (action.includes("create") || action.includes("add")) {
    return "bg-blue-950/40 border-blue-500 text-blue-300";
  }
  if (action.includes("update") || action.includes("modify")) {
    return "bg-amber-950/40 border-amber-500 text-amber-300";
  }
  if (action.includes("delete") || action.includes("remove")) {
    return "bg-red-950/40 border-red-500 text-red-300";
  }
  if (action.includes("verify")) {
    return "bg-green-950/40 border-green-500 text-green-300";
  }
  return "bg-surface-subtle border-surface-border text-ink-dim";
}

/**
 * Get timeline node icon based on action
 */
function getActionIcon(action: string): string {
  if (action.includes("create") || action.includes("add")) return "✚";
  if (action.includes("update") || action.includes("modify")) return "◐";
  if (action.includes("delete") || action.includes("remove")) return "✕";
  if (action.includes("verify")) return "✓";
  return "•";
}

/**
 * Format timestamp as relative time (e.g., "2m ago")
 */
function formatRelativeTime(ts: string): string {
  const date = new Date(ts);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

// React.useMemo shim for memoization
function useMemo<T>(factory: () => T, deps: React.DependencyList): T {
  const ref = React.useRef<{ deps: React.DependencyList; value: T } | null>(null);

  if (
    !ref.current ||
    deps.length !== ref.current.deps.length ||
    deps.some((dep, i) => dep !== ref.current!.deps[i])
  ) {
    ref.current = { deps, value: factory() };
  }

  return ref.current.value;
}
