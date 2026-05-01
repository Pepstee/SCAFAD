/**
 * Render a coloured pill for case lifecycle state.  Used in CaseDrawer
 * header and Cases page rows.
 */

import { clsx } from "@/lib/format";
import type { CaseStatus } from "@/lib/types";

const STATE_TONE: Record<CaseStatus, string> = {
  open: "var(--sev-escalate)",
  triage: "var(--sev-review)",
  contained: "#5b8cff",
  closed: "var(--sev-observe)",
};

const STATE_LABEL: Record<CaseStatus, string> = {
  open: "Open",
  triage: "Triage",
  contained: "Contained",
  closed: "Closed",
};

interface StatePillProps {
  status: CaseStatus;
  className?: string;
}

export function StatePill({ status, className }: StatePillProps) {
  const color = STATE_TONE[status];
  return (
    <span
      data-testid={`state-pill-${status}`}
      className={clsx(
        "inline-flex items-center gap-1 rounded-full border bg-surface-subtle px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide",
        className
      )}
      style={{ borderColor: color, color }}
    >
      <span
        aria-hidden
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: color }}
      />
      {STATE_LABEL[status]}
    </span>
  );
}
