/**
 * Sticky filter bar for the Detection Inbox.
 *
 * Implementation note: filters are URL-state-backed (the parent page reads
 * and writes them via ``useSearchParams``).  This component is therefore a
 * controlled view: it receives the resolved ``InboxFilters`` and emits a
 * mutation request via ``onChange`` whenever a chip toggles.
 */

import { useMemo, useState } from "react";
import { clsx } from "@/lib/format";
import type { CaseStatus, InboxFilters, Severity } from "@/lib/types";

interface FilterBarProps {
  filters: InboxFilters;
  onChange: (next: InboxFilters) => void;
  onReset: () => void;
  knownAnomalyTypes?: string[];
  knownTechniques?: string[];
}

const SEVERITY_OPTIONS: Severity[] = ["observe", "review", "escalate"];
const TIME_WINDOWS: Array<{ key: string; label: string; sinceMinutes: number | null }> = [
  { key: "1h", label: "Last 1h", sinceMinutes: 60 },
  { key: "24h", label: "24h", sinceMinutes: 60 * 24 },
  { key: "7d", label: "7d", sinceMinutes: 60 * 24 * 7 },
  { key: "30d", label: "30d", sinceMinutes: 60 * 24 * 30 },
  { key: "all", label: "All", sinceMinutes: null },
];
const CASE_STATUS_OPTIONS: Array<{ key: CaseStatus | "none" | "any"; label: string }> = [
  { key: "any", label: "Any" },
  { key: "none", label: "Unlinked" },
  { key: "open", label: "Open" },
  { key: "triage", label: "Triage" },
  { key: "contained", label: "Contained" },
  { key: "closed", label: "Closed" },
];

function toggleInArray(values: string[] | undefined, item: string): string[] {
  const cur = values ? [...values] : [];
  const idx = cur.indexOf(item);
  if (idx >= 0) cur.splice(idx, 1);
  else cur.push(item);
  return cur;
}

export function FilterBar({
  filters,
  onChange,
  onReset,
  knownAnomalyTypes = [],
  knownTechniques = [],
}: FilterBarProps) {
  const [textDraft, setTextDraft] = useState(filters.text ?? "");

  const activeWindow = useMemo(() => {
    if (!filters.since) return "all";
    const minutes = (Date.now() - new Date(filters.since).getTime()) / 60_000;
    let best = "all";
    let bestDelta = Number.POSITIVE_INFINITY;
    for (const w of TIME_WINDOWS) {
      if (w.sinceMinutes === null) continue;
      const delta = Math.abs(w.sinceMinutes - minutes);
      if (delta < bestDelta) {
        best = w.key;
        bestDelta = delta;
      }
    }
    return best;
  }, [filters.since]);

  return (
    <div
      data-testid="inbox-filter-bar"
      className="flex flex-wrap items-center gap-2 border-b border-surface-border bg-surface-panel px-4 py-3 text-xs"
    >
      {/* Severity */}
      <FilterGroup label="Severity">
        {SEVERITY_OPTIONS.map((sev) => {
          const active = (filters.severity ?? []).includes(sev);
          return (
            <Pill
              key={sev}
              active={active}
              onClick={() =>
                onChange({
                  ...filters,
                  severity: toggleInArray(filters.severity, sev) as Severity[],
                })
              }
            >
              {sev}
            </Pill>
          );
        })}
      </FilterGroup>

      {/* Anomaly type */}
      {knownAnomalyTypes.length > 0 && (
        <FilterGroup label="Anomaly">
          {knownAnomalyTypes.slice(0, 8).map((typ) => {
            const active = (filters.anomaly_type ?? []).includes(typ);
            return (
              <Pill
                key={typ}
                active={active}
                onClick={() =>
                  onChange({
                    ...filters,
                    anomaly_type: toggleInArray(filters.anomaly_type, typ),
                  })
                }
              >
                {typ}
              </Pill>
            );
          })}
        </FilterGroup>
      )}

      {/* MITRE technique */}
      {knownTechniques.length > 0 && (
        <FilterGroup label="MITRE">
          {knownTechniques.slice(0, 6).map((t) => {
            const active = (filters.mitre_technique ?? []).includes(t);
            return (
              <Pill
                key={t}
                active={active}
                onClick={() =>
                  onChange({
                    ...filters,
                    mitre_technique: toggleInArray(filters.mitre_technique, t),
                  })
                }
              >
                {t}
              </Pill>
            );
          })}
        </FilterGroup>
      )}

      {/* Time window */}
      <FilterGroup label="Window">
        {TIME_WINDOWS.map((w) => (
          <Pill
            key={w.key}
            active={activeWindow === w.key}
            onClick={() => {
              if (w.sinceMinutes === null) {
                onChange({ ...filters, since: undefined });
              } else {
                const since = new Date(Date.now() - w.sinceMinutes * 60_000).toISOString();
                onChange({ ...filters, since });
              }
            }}
          >
            {w.label}
          </Pill>
        ))}
      </FilterGroup>

      {/* Case status */}
      <FilterGroup label="Case">
        {CASE_STATUS_OPTIONS.map((opt) => {
          const active =
            (opt.key === "any" && !filters.case_status) || filters.case_status === opt.key;
          return (
            <Pill
              key={opt.key}
              active={active}
              onClick={() => {
                if (opt.key === "any") {
                  onChange({ ...filters, case_status: undefined });
                } else {
                  onChange({ ...filters, case_status: opt.key });
                }
              }}
            >
              {opt.label}
            </Pill>
          );
        })}
      </FilterGroup>

      {/* Text search */}
      <label className="ml-auto flex items-center gap-2">
        <span className="uppercase tracking-wide text-surface-muted">Search</span>
        <input
          aria-label="Inbox text search"
          value={textDraft}
          onChange={(e) => setTextDraft(e.target.value)}
          onBlur={() => onChange({ ...filters, text: textDraft || undefined })}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              onChange({ ...filters, text: textDraft || undefined });
            }
          }}
          placeholder="event_id / function_id / correlation"
          className="w-64 rounded border border-surface-border bg-surface-subtle px-2 py-1 text-xs text-ink placeholder:text-surface-muted focus:border-ink-accent focus:outline-none"
        />
      </label>
      <button
        type="button"
        onClick={() => {
          setTextDraft("");
          onReset();
        }}
        className="rounded border border-surface-border px-2 py-1 text-[11px] uppercase tracking-wide text-ink-dim hover:bg-surface-subtle"
      >
        Reset
      </button>
    </div>
  );
}

interface FilterGroupProps {
  label: string;
  children: React.ReactNode;
}

function FilterGroup({ label, children }: FilterGroupProps) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-[10px] uppercase tracking-wider text-surface-muted">
        {label}
      </span>
      <div className="flex flex-wrap items-center gap-1">{children}</div>
    </div>
  );
}

interface PillProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

function Pill({ active, onClick, children }: PillProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "rounded-full border px-2 py-0.5 text-[11px] capitalize transition-colors",
        active
          ? "border-ink-accent bg-[rgba(91,140,255,0.18)] text-ink"
          : "border-surface-border bg-surface-subtle text-ink-dim hover:text-ink"
      )}
    >
      {children}
    </button>
  );
}
