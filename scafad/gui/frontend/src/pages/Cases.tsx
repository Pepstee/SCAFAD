import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Card } from "@/components/ui/Card";
import { Empty } from "@/components/ui/Empty";
import { Skeleton } from "@/components/ui/Skeleton";
import { SeverityChip } from "@/components/ui/SeverityChip";
import { CaseDrawer } from "@/components/cases/CaseDrawer";
import { StatePill } from "@/components/cases/StatePill";

import { api, queryKeys, useCaseStream } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import type { CaseStatus, CaseSummary } from "@/lib/types";

const STATE_FILTERS: Array<{ key: CaseStatus | "all"; label: string }> = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "triage", label: "Triage" },
  { key: "contained", label: "Contained" },
  { key: "closed", label: "Closed" },
];

const ASSIGNEE_FILTERS = [
  { key: "all", label: "Anyone" },
  { key: "analyst@scafad.local", label: "Primary Analyst" },
  { key: "analyst-2@scafad.local", label: "Secondary Analyst" },
  { key: "unassigned", label: "Unassigned" },
];

export default function CasesPage() {
  useCaseStream();
  const [statusFilter, setStatusFilter] = useState<CaseStatus | "all">("all");
  const [assigneeFilter, setAssigneeFilter] = useState<string>("all");
  const [drawerCaseId, setDrawerCaseId] = useState<string | null>(null);

  const params = useMemo(() => {
    const out: { status?: CaseStatus; assignee_id?: string } = {};
    if (statusFilter !== "all") out.status = statusFilter as CaseStatus;
    if (assigneeFilter === "unassigned") out.assignee_id = "";
    else if (assigneeFilter !== "all") out.assignee_id = assigneeFilter;
    return out;
  }, [statusFilter, assigneeFilter]);

  const casesQuery = useQuery({
    queryKey: queryKeys.cases(params),
    queryFn: () => api.listCases({ ...params, page_size: 100 }),
    refetchInterval: 30_000,
  });
  const items: CaseSummary[] = casesQuery.data?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Cases</h1>
          <p className="mt-1 text-sm text-surface-muted">
            Investigation lifecycle: open → triage → contained → closed.
          </p>
        </div>
      </header>

      <Card className="overflow-hidden p-0">
        <div className="flex flex-wrap items-center gap-3 border-b border-surface-border bg-surface-panel px-4 py-2 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-wider text-surface-muted">
              Status
            </span>
            {STATE_FILTERS.map((opt) => (
              <button
                key={opt.key}
                type="button"
                onClick={() => setStatusFilter(opt.key)}
                className={
                  statusFilter === opt.key
                    ? "rounded-full border border-ink-accent bg-[rgba(91,140,255,0.18)] px-2 py-0.5 text-ink"
                    : "rounded-full border border-surface-border bg-surface-subtle px-2 py-0.5 text-ink-dim hover:text-ink"
                }
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-2">
            <label className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-wider text-surface-muted">
                Assignee
              </span>
              <select
                aria-label="Assignee filter"
                value={assigneeFilter}
                onChange={(e) => setAssigneeFilter(e.target.value)}
                className="rounded border border-surface-border bg-surface-subtle px-2 py-1 text-ink focus:border-ink-accent focus:outline-none"
              >
                {ASSIGNEE_FILTERS.map((opt) => (
                  <option key={opt.key} value={opt.key}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {casesQuery.isLoading ? (
          <div className="p-6">
            <Skeleton className="h-40 w-full" />
          </div>
        ) : items.length === 0 ? (
          <Empty
            title="No cases yet"
            body="Open a case from the Inbox by selecting detections and choosing 'Open new case'."
          />
        ) : (
          <table className="min-w-full text-xs" data-testid="cases-table">
            <thead>
              <tr className="border-b border-surface-border text-left text-[11px] uppercase tracking-wide text-surface-muted">
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Title</th>
                <th className="px-3 py-2">Severity</th>
                <th className="px-3 py-2">Assignee</th>
                <th className="px-3 py-2 text-right">Detections</th>
                <th className="px-3 py-2">Opened</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr
                  key={c.id}
                  data-testid={`case-row-${c.id}`}
                  onClick={() => setDrawerCaseId(c.id)}
                  className="cursor-pointer border-b border-surface-border/60 transition-colors hover:bg-surface-subtle"
                >
                  <td className="px-3 py-2">
                    <StatePill status={c.status} />
                  </td>
                  <td className="px-3 py-2 text-ink">{c.title}</td>
                  <td className="px-3 py-2">
                    <SeverityChip severity={c.severity_rollup} compact />
                  </td>
                  <td className="px-3 py-2 text-ink-dim">
                    {c.assignee_id ?? "Unassigned"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink">
                    {c.detection_count}
                  </td>
                  <td className="px-3 py-2 text-surface-muted">
                    {formatRelativeTime(c.opened_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <CaseDrawer
        caseId={drawerCaseId}
        open={Boolean(drawerCaseId)}
        onClose={() => setDrawerCaseId(null)}
      />
    </div>
  );
}
