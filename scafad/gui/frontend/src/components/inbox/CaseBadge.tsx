/**
 * Pill rendering case status + (truncated) title.  Clicking opens the
 * Case drawer (handled by the parent).
 */

import { clsx } from "@/lib/format";
import type { CaseSummary } from "@/lib/types";

interface CaseBadgeProps {
  case_: CaseSummary | null | undefined;
  onClick?: (caseSummary: CaseSummary) => void;
}

const STATE_TONE: Record<string, string> = {
  open: "var(--sev-escalate)",
  triage: "var(--sev-review)",
  contained: "var(--sev-info, #5b8cff)",
  closed: "var(--sev-observe)",
};

export function CaseBadge({ case_, onClick }: CaseBadgeProps) {
  if (!case_) {
    return <span className="text-[11px] text-surface-muted">—</span>;
  }
  const color = STATE_TONE[case_.status] ?? "var(--sev-info, #5b8cff)";
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onClick?.(case_);
      }}
      data-testid={`case-badge-${case_.id}`}
      className={clsx(
        "inline-flex max-w-[180px] items-center gap-1 truncate rounded-full border px-2 py-0.5 text-[11px]"
      )}
      style={{ borderColor: color, color }}
      title={`${case_.title} (${case_.status})`}
    >
      <span aria-hidden className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      <span className="truncate uppercase tracking-wide">{case_.status}</span>
      <span className="truncate text-ink-dim normal-case">· {case_.title}</span>
    </button>
  );
}
