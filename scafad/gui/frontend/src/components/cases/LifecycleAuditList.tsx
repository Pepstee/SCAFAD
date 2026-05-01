/**
 * Append-only audit feed for a case.  Renders newest-first by default.
 */

import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "@/lib/api";
import { formatRelativeTime, formatTimestamp } from "@/lib/format";
import type { CaseEvent } from "@/lib/types";

interface LifecycleAuditListProps {
  caseId: string;
}

const KIND_LABEL: Record<string, string> = {
  created: "Case created",
  state_changed: "State changed",
  assigned: "Assignee changed",
  commented: "Comment posted",
  detection_attached: "Detection attached",
  detection_detached: "Detection detached",
  dismissed: "Dismissed",
  reopened: "Reopened",
};

function summary(event: CaseEvent): string {
  const p = event.payload ?? {};
  switch (event.kind) {
    case "state_changed":
    case "reopened":
      return `${p.from ?? "?"} → ${p.to ?? "?"}${p.reason ? ` (${p.reason})` : ""}`;
    case "assigned":
      return `${p.from ?? "—"} → ${p.to ?? "—"}`;
    case "detection_attached":
    case "detection_detached":
      return String(p.detection_id ?? "");
    case "commented":
      return String(p.preview ?? "");
    case "created":
      return String(p.title ?? "");
    default:
      return "";
  }
}

export function LifecycleAuditList({ caseId }: LifecycleAuditListProps) {
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.caseEvents(caseId),
    queryFn: () => api.listCaseEvents(caseId),
    enabled: Boolean(caseId),
  });
  const items: CaseEvent[] = data?.items ?? [];
  const ordered = [...items].sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  if (isLoading) return <p className="text-xs text-surface-muted">Loading…</p>;
  if (ordered.length === 0) {
    return <p className="text-xs text-surface-muted">No lifecycle events yet.</p>;
  }
  return (
    <ol data-testid="lifecycle-audit-list" className="flex flex-col gap-2">
      {ordered.map((event) => (
        <li
          key={event.id}
          className="rounded border border-surface-border bg-surface-subtle px-3 py-2 text-xs"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium text-ink">
              {KIND_LABEL[event.kind] ?? event.kind}
            </span>
            <span
              className="text-[11px] text-surface-muted"
              title={formatTimestamp(event.created_at)}
            >
              {formatRelativeTime(event.created_at)}
            </span>
          </div>
          <div className="mt-1 text-ink-dim">
            <span className="font-mono text-[11px]">{event.actor_id}</span>
            {summary(event) && <span> · {summary(event)}</span>}
          </div>
        </li>
      ))}
    </ol>
  );
}
