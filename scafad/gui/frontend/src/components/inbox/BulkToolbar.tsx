/**
 * Bulk-action toolbar surfaced when ≥ 1 inbox row is selected.
 *
 * Actions: Assign to me / Attach to case / Open new case / Dismiss / Export.
 * The toolbar emits ``onAction`` callbacks; the parent owns the API plumbing
 * so this component stays test-friendly.
 */

import { useState } from "react";
import type { BulkActionType, CaseSummary, InboxFilters } from "@/lib/types";

interface BulkToolbarProps {
  selectedCount: number;
  onAction: (action: BulkActionType, payload?: Record<string, unknown>) => void;
  onClearSelection: () => void;
  exportHref: string;
  cases?: CaseSummary[];
}

export function BulkToolbar({
  selectedCount,
  onAction,
  onClearSelection,
  exportHref,
  cases = [],
}: BulkToolbarProps) {
  const [attachOpen, setAttachOpen] = useState(false);

  if (selectedCount <= 0) return null;

  return (
    <div
      data-testid="bulk-toolbar"
      role="toolbar"
      aria-label="Bulk actions"
      className="flex flex-wrap items-center gap-2 border-b border-surface-border bg-[rgba(91,140,255,0.08)] px-4 py-2 text-xs text-ink"
    >
      <span className="font-medium">{selectedCount} selected</span>

      <button
        type="button"
        onClick={() => onAction("assign", { assignee_id: "analyst@scafad.local" })}
        className="rounded border border-surface-border bg-surface-panel px-2 py-1 hover:bg-surface-subtle"
      >
        Assign to me
      </button>

      <div className="relative">
        <button
          type="button"
          onClick={() => setAttachOpen((v) => !v)}
          className="rounded border border-surface-border bg-surface-panel px-2 py-1 hover:bg-surface-subtle"
        >
          Attach to case ▾
        </button>
        {attachOpen && (
          <div className="absolute z-50 mt-1 w-72 rounded border border-surface-border bg-surface-panel p-2 shadow-lg">
            {cases.length === 0 ? (
              <p className="px-2 py-1 text-surface-muted">No open cases — open a new one.</p>
            ) : (
              <ul className="max-h-60 divide-y divide-surface-border overflow-y-auto">
                {cases.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => {
                        onAction("attach", { case_id: c.id });
                        setAttachOpen(false);
                      }}
                      className="block w-full truncate rounded px-2 py-1 text-left hover:bg-surface-subtle"
                    >
                      <span className="font-medium">{c.title}</span>
                      <span className="ml-2 text-[10px] uppercase tracking-wide text-surface-muted">
                        {c.status}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => {
          const title = window.prompt("Case title", "New investigation") || "";
          if (title) onAction("open_case", { title });
        }}
        className="rounded border border-surface-border bg-surface-panel px-2 py-1 hover:bg-surface-subtle"
      >
        Open new case
      </button>

      <button
        type="button"
        onClick={() => {
          const reason = window.prompt("Dismiss reason", "false positive") || "";
          onAction("dismiss", { reason });
        }}
        className="rounded border border-surface-border bg-surface-panel px-2 py-1 hover:bg-surface-subtle"
      >
        Dismiss
      </button>

      <a
        href={exportHref}
        download
        className="rounded border border-surface-border bg-surface-panel px-2 py-1 text-ink hover:bg-surface-subtle"
      >
        Export CSV
      </a>

      <button
        type="button"
        onClick={onClearSelection}
        className="ml-auto rounded px-2 py-1 text-surface-muted hover:text-ink"
      >
        Clear selection
      </button>
    </div>
  );
}
