/**
 * Markdown comment list + composer.
 *
 * Phase 2 keeps the markdown rendering minimal — we whitelist a tiny set of
 * inline tokens (bold/italic/code/links) and escape everything else.  Adding
 * `react-markdown` + `rehype-sanitize` is left to Phase 5 when the bundle
 * has more time to be measured.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, queryKeys } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import type { Comment } from "@/lib/types";

interface CommentsProps {
  caseId: string;
}

function escapeHtml(input: string): string {
  return input
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/**
 * Tiny safe markdown renderer.  Supports:
 *  - `**bold**` / `__bold__`
 *  - `*italic*` / `_italic_`
 *  - `` `code` ``
 *  - `[label](https://safe-url)`
 *  - paragraph + line-break preservation
 *
 * Everything else is HTML-escaped, so user input cannot inject script tags.
 */
export function renderMarkdown(input: string): string {
  const safe = escapeHtml(input);
  const linked = safe.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_m, label: string, url: string) =>
      `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`
  );
  const formatted = linked
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/_([^_]+)_/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
  return formatted.split(/\n{2,}/).map((p) => `<p>${p.replaceAll("\n", "<br/>")}</p>`).join("");
}

export function Comments({ caseId }: CommentsProps) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const [showPreview, setShowPreview] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.caseComments(caseId),
    queryFn: () => api.listComments(caseId),
    enabled: Boolean(caseId),
  });
  const items: Comment[] = data?.items ?? [];

  const addMut = useMutation({
    mutationFn: (body_md: string) => api.addComment(caseId, { body_md }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.caseComments(caseId) });
      qc.invalidateQueries({ queryKey: queryKeys.caseEvents(caseId) });
      setDraft("");
      setShowPreview(false);
    },
  });

  return (
    <div data-testid="comments" className="flex flex-col gap-3">
      {isLoading && <p className="text-xs text-surface-muted">Loading comments…</p>}
      {items.length === 0 && !isLoading && (
        <p className="text-xs text-surface-muted">No comments yet.</p>
      )}
      <ul className="flex flex-col gap-2">
        {items.map((c) => (
          <li
            key={c.id}
            className="rounded border border-surface-border bg-surface-subtle px-3 py-2 text-sm text-ink"
          >
            <header className="mb-1 flex items-center justify-between text-[11px] text-surface-muted">
              <span>{c.author_id}</span>
              <span>{formatRelativeTime(c.created_at)}</span>
            </header>
            <div
              className="prose prose-invert max-w-none text-sm"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(c.body_md) }}
            />
          </li>
        ))}
      </ul>

      <form
        data-testid="comment-composer"
        onSubmit={(e) => {
          e.preventDefault();
          if (!draft.trim()) return;
          addMut.mutate(draft.trim());
        }}
        className="flex flex-col gap-2 rounded border border-surface-border bg-surface-panel p-2"
      >
        <textarea
          aria-label="Comment body"
          rows={3}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Write a comment (Markdown supported)…"
          className="rounded border border-surface-border bg-surface-subtle px-2 py-1 text-sm text-ink placeholder:text-surface-muted focus:border-ink-accent focus:outline-none"
        />
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setShowPreview((v) => !v)}
            className="rounded border border-surface-border px-2 py-1 text-[11px] uppercase tracking-wide text-ink-dim hover:text-ink"
          >
            {showPreview ? "Hide preview" : "Preview"}
          </button>
          <button
            type="submit"
            disabled={!draft.trim() || addMut.isPending}
            className="rounded bg-[rgba(91,140,255,0.18)] px-3 py-1 text-xs text-ink hover:bg-[rgba(91,140,255,0.3)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {addMut.isPending ? "Posting…" : "Post comment"}
          </button>
        </div>
        {showPreview && draft.trim() && (
          <div
            data-testid="comment-preview"
            className="rounded border border-surface-border bg-surface-subtle px-2 py-1 text-sm text-ink"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(draft) }}
          />
        )}
      </form>
    </div>
  );
}
