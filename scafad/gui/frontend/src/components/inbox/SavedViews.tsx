/**
 * Saved-views dropdown for the Detection Inbox.
 *
 * The component is intentionally minimal: it renders a button + popover
 * pattern using only inline state (no Radix dependency) so the bundle stays
 * lean.  Tests assert the visible labels and the API calls that flow
 * through.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, queryKeys } from "@/lib/api";
import type { InboxFilters, SavedView } from "@/lib/types";
import { clsx } from "@/lib/format";

interface SavedViewsProps {
  filters: InboxFilters;
  onApply: (view: SavedView) => void;
}

export function SavedViews({ filters, onApply }: SavedViewsProps) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState("");

  const { data } = useQuery({
    queryKey: queryKeys.views,
    queryFn: () => api.listViews(),
  });
  const views = data?.items ?? [];

  const createMut = useMutation({
    mutationFn: (name: string) =>
      api.createView({ name, filter_json: filters as unknown as Record<string, unknown> }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.views }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteView(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.views }),
  });

  const handleSave = () => {
    const name = renaming.trim() || `View ${views.length + 1}`;
    createMut.mutate(name);
    setRenaming("");
    setOpen(false);
  };

  return (
    <div data-testid="saved-views" className="relative inline-block text-left">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="rounded border border-surface-border bg-surface-subtle px-3 py-1 text-xs text-ink-dim hover:text-ink"
      >
        Saved views {views.length > 0 ? `(${views.length})` : ""}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-1 w-72 rounded border border-surface-border bg-surface-panel p-2 text-xs shadow-lg"
        >
          {views.length === 0 ? (
            <p className="px-2 py-1 text-surface-muted">No saved views yet.</p>
          ) : (
            <ul className="divide-y divide-surface-border">
              {views.map((v) => (
                <li
                  key={v.id}
                  className="flex items-center justify-between gap-2 py-1"
                >
                  <button
                    type="button"
                    className={clsx(
                      "flex-1 truncate rounded px-2 py-1 text-left text-ink hover:bg-surface-subtle",
                      v.pinned && "font-semibold"
                    )}
                    onClick={() => {
                      onApply(v);
                      setOpen(false);
                    }}
                  >
                    {v.pinned && <span aria-hidden>★ </span>}
                    {v.name}
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteMut.mutate(v.id)}
                    className="rounded px-1.5 text-[11px] text-surface-muted hover:text-ink"
                    title="Delete view"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-2 border-t border-surface-border pt-2">
            <input
              type="text"
              placeholder="Save current filters as…"
              value={renaming}
              onChange={(e) => setRenaming(e.target.value)}
              className="w-full rounded border border-surface-border bg-surface-subtle px-2 py-1 text-ink placeholder:text-surface-muted focus:border-ink-accent focus:outline-none"
            />
            <button
              type="button"
              onClick={handleSave}
              className="mt-2 w-full rounded bg-[rgba(91,140,255,0.18)] px-2 py-1 text-ink hover:bg-[rgba(91,140,255,0.3)]"
            >
              Save view
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
