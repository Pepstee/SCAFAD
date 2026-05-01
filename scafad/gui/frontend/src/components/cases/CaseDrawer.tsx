/**
 * Slide-over drawer that renders a case across four tabs:
 * Overview / Detections / Comments / Lifecycle.
 *
 * The drawer is implemented inline (no Radix dependency) so the bundle
 * stays small.  Closing on Escape and outside-click is wired up via
 * a ``useEffect``.
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, queryKeys } from "@/lib/api";
import { clsx, formatTimestamp } from "@/lib/format";
import { SeverityChip } from "@/components/ui/SeverityChip";
import { AssigneePicker } from "./AssigneePicker";
import { Comments } from "./Comments";
import { LifecycleAuditList } from "./LifecycleAuditList";
import { StatePill } from "./StatePill";
import type {
  CaseStatus,
  DetectionListResponse,
} from "@/lib/types";

interface CaseDrawerProps {
  caseId: string | null;
  open: boolean;
  onClose: () => void;
}

const STATE_OPTIONS: CaseStatus[] = ["open", "triage", "contained", "closed"];

export function CaseDrawer({ caseId, open, onClose }: CaseDrawerProps) {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"overview" | "detections" | "comments" | "lifecycle">(
    "overview"
  );
  const [versionConflict, setVersionConflict] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const caseQuery = useQuery({
    queryKey: caseId ? queryKeys.case(caseId) : ["case", "none"],
    queryFn: () => api.getCase(caseId as string),
    enabled: open && Boolean(caseId),
  });
  const detectionsQuery = useQuery<DetectionListResponse>({
    queryKey: caseId ? queryKeys.caseDetections(caseId) : ["case", "none", "detections"],
    queryFn: () => api.listCaseDetections(caseId as string),
    enabled: open && Boolean(caseId) && tab === "detections",
  });

  const patchMut = useMutation({
    mutationFn: (patch: { status?: CaseStatus; assignee_id?: string | null }) => {
      if (!caseQuery.data) throw new Error("case not loaded");
      return api.patchCase(caseQuery.data.id, {
        expected_version: caseQuery.data.version,
        ...patch,
      });
    },
    onSuccess: () => {
      setVersionConflict(false);
      qc.invalidateQueries({ queryKey: queryKeys.cases() });
      if (caseId) {
        qc.invalidateQueries({ queryKey: queryKeys.case(caseId) });
        qc.invalidateQueries({ queryKey: queryKeys.caseEvents(caseId) });
      }
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("409")) {
        setVersionConflict(true);
        if (caseId) {
          qc.invalidateQueries({ queryKey: queryKeys.case(caseId) });
        }
      }
    },
  });

  if (!open || !caseId) return null;

  const c = caseQuery.data;

  return (
    <>
      <div
        data-testid="case-drawer-overlay"
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/40"
      />
      <aside
        data-testid="case-drawer"
        role="dialog"
        aria-label="Case drawer"
        className="fixed right-0 top-0 z-50 flex h-full w-[520px] max-w-full flex-col border-l border-surface-border bg-surface-panel shadow-xl"
      >
        <header className="flex items-start gap-3 border-b border-surface-border px-4 py-3">
          <div className="flex flex-1 flex-col gap-1">
            {!c ? (
              <span className="text-sm text-surface-muted">Loading case…</span>
            ) : (
              <>
                <div className="flex items-center gap-2 text-xs">
                  <StatePill status={c.status} />
                  <SeverityChip severity={c.severity_rollup} compact />
                  <span className="text-surface-muted">v{c.version}</span>
                </div>
                <h2 className="text-sm font-semibold text-ink">{c.title}</h2>
                <p className="text-[11px] text-surface-muted">
                  Opened {formatTimestamp(c.opened_at)} · created by {c.created_by}
                </p>
              </>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            className="rounded px-2 py-1 text-surface-muted hover:text-ink"
          >
            ×
          </button>
        </header>

        {versionConflict && (
          <div
            data-testid="version-conflict-banner"
            role="alert"
            className="border-b border-[var(--sev-review)] bg-[rgba(245,165,36,0.1)] px-4 py-2 text-xs text-[var(--sev-review)]"
          >
            Another analyst updated this case. The view has been refreshed —
            please review and re-submit your change.
          </div>
        )}

        {c && (
          <div className="flex flex-wrap items-center gap-2 border-b border-surface-border px-4 py-2 text-xs">
            <label className="flex items-center gap-2">
              <span className="text-surface-muted">State</span>
              <select
                aria-label="Case state"
                value={c.status}
                disabled={patchMut.isPending}
                onChange={(e) =>
                  patchMut.mutate({ status: e.target.value as CaseStatus })
                }
                className="rounded border border-surface-border bg-surface-subtle px-2 py-1 text-ink focus:border-ink-accent focus:outline-none"
              >
                {STATE_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2">
              <span className="text-surface-muted">Assignee</span>
              <AssigneePicker
                value={c.assignee_id}
                disabled={patchMut.isPending}
                onChange={(value) =>
                  patchMut.mutate({ assignee_id: value ?? "" })
                }
              />
            </label>
          </div>
        )}

        <nav
          data-testid="case-drawer-tabs"
          className="flex items-center border-b border-surface-border px-2 text-xs"
        >
          {(
            [
              ["overview", "Overview"],
              ["detections", "Detections"],
              ["comments", "Comments"],
              ["lifecycle", "Lifecycle"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={clsx(
                "px-3 py-2 transition-colors",
                tab === key
                  ? "border-b-2 border-ink-accent text-ink"
                  : "text-ink-dim hover:text-ink"
              )}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className="flex-1 overflow-y-auto px-4 py-3 text-sm">
          {!c ? null : tab === "overview" ? (
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <dt className="text-surface-muted">Detections</dt>
              <dd className="font-mono text-ink">{c.detection_count}</dd>
              <dt className="text-surface-muted">Severity rollup</dt>
              <dd className="text-ink">{c.severity_rollup}</dd>
              <dt className="text-surface-muted">Closed at</dt>
              <dd className="text-ink">
                {c.closed_at ? formatTimestamp(c.closed_at) : "—"}
              </dd>
              <dt className="text-surface-muted">Version</dt>
              <dd className="font-mono text-ink">{c.version}</dd>
            </dl>
          ) : tab === "detections" ? (
            <ul className="flex flex-col gap-1 text-xs">
              {(detectionsQuery.data?.items ?? []).length === 0 ? (
                <li className="text-surface-muted">No detections linked.</li>
              ) : (
                (detectionsQuery.data?.items ?? []).map((d) => (
                  <li
                    key={d.id}
                    className="flex items-center justify-between rounded border border-surface-border bg-surface-subtle px-2 py-1"
                  >
                    <span className="font-mono text-ink">{d.event_id}</span>
                    <SeverityChip severity={d.severity} compact />
                  </li>
                ))
              )}
            </ul>
          ) : tab === "comments" ? (
            <Comments caseId={c.id} />
          ) : (
            <LifecycleAuditList caseId={c.id} />
          )}
        </div>
      </aside>
    </>
  );
}
