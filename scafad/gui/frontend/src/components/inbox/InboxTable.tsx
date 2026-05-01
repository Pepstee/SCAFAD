/**
 * Inbox triage table.
 *
 * Renders a dense, sortable, keyboard-navigable list of detection rows.
 * Selection state is owned by the parent so URL state can persist between
 * navigations; this component is a controlled view.
 */

import { useEffect, useRef } from "react";
import { clsx, formatRelativeTime } from "@/lib/format";
import { SeverityChip } from "@/components/ui/SeverityChip";
import { CaseBadge } from "./CaseBadge";
import type { CaseSummary, DetectionSummary } from "@/lib/types";

interface InboxTableProps {
  rows: DetectionSummary[];
  caseByDetection: Record<string, CaseSummary | undefined>;
  selected: Set<string>;
  onToggleSelected: (id: string) => void;
  onToggleAll: () => void;
  focusedIndex: number;
  setFocusedIndex: (idx: number) => void;
  onOpenDetail: (row: DetectionSummary) => void;
  onOpenCase: (caseSummary: CaseSummary) => void;
}

export function InboxTable({
  rows,
  caseByDetection,
  selected,
  onToggleSelected,
  onToggleAll,
  focusedIndex,
  setFocusedIndex,
  onOpenDetail,
  onOpenCase,
}: InboxTableProps) {
  const tbodyRef = useRef<HTMLTableSectionElement | null>(null);

  useEffect(() => {
    const node = tbodyRef.current?.querySelector(
      `tr[data-row-index="${focusedIndex}"]`
    ) as HTMLElement | null;
    // jsdom (used in Vitest) does not implement Element.scrollIntoView.
    // Guard so the test environment never throws on focus tracking.
    if (node && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ block: "nearest" });
    }
  }, [focusedIndex]);

  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));

  return (
    <div className="w-full overflow-x-auto">
      <table className="min-w-full text-xs" data-testid="inbox-table">
        <thead className="sticky top-0 bg-surface-panel">
          <tr className="border-b border-surface-border text-left text-[11px] uppercase tracking-wide text-surface-muted">
            <th className="px-3 py-2">
              <input
                type="checkbox"
                aria-label="Select all rows"
                checked={allSelected}
                onChange={onToggleAll}
              />
            </th>
            <th className="px-3 py-2">When</th>
            <th className="px-3 py-2">Severity</th>
            <th className="px-3 py-2">Function</th>
            <th className="px-3 py-2">Anomaly</th>
            <th className="px-3 py-2">MITRE</th>
            <th className="px-3 py-2 text-right">Trust</th>
            <th className="px-3 py-2">Case</th>
          </tr>
        </thead>
        <tbody ref={tbodyRef}>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={8} className="px-3 py-12 text-center text-surface-muted">
                No detections match these filters.
              </td>
            </tr>
          ) : (
            rows.map((row, idx) => {
              const isSelected = selected.has(row.id);
              const isFocused = idx === focusedIndex;
              const linkedCase = caseByDetection[row.id];
              const techniques = row.mitre_techniques.slice(0, 3);
              const overflow = row.mitre_techniques.length - techniques.length;
              return (
                <tr
                  key={row.id}
                  data-row-index={idx}
                  data-testid={`inbox-row-${row.id}`}
                  onClick={() => {
                    setFocusedIndex(idx);
                    onOpenDetail(row);
                  }}
                  className={clsx(
                    "border-b border-surface-border/60 transition-colors hover:bg-surface-subtle",
                    isFocused && "bg-[rgba(91,140,255,0.08)]",
                    isSelected && "ring-1 ring-[rgba(91,140,255,0.4)]"
                  )}
                >
                  <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label={`Select detection ${row.event_id}`}
                      checked={isSelected}
                      onChange={() => onToggleSelected(row.id)}
                    />
                  </td>
                  <td className="px-3 py-2 text-surface-muted">
                    {formatRelativeTime(row.ingested_at)}
                  </td>
                  <td className="px-3 py-2">
                    <SeverityChip severity={row.severity} compact />
                  </td>
                  <td className="px-3 py-2 font-mono text-ink">{row.function_id}</td>
                  <td className="px-3 py-2">{row.anomaly_type}</td>
                  <td className="px-3 py-2 font-mono text-[10px] text-ink-dim">
                    {techniques.length === 0
                      ? "—"
                      : techniques.join(", ") + (overflow > 0 ? ` +${overflow}` : "")}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {row.trust_score.toFixed(2)}
                  </td>
                  <td className="px-3 py-2">
                    <CaseBadge case_={linkedCase ?? null} onClick={onOpenCase} />
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
