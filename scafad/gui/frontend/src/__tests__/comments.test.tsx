import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { Comments, renderMarkdown } from "@/components/cases/Comments";

const COMMENTS = {
  items: [
    {
      id: "k-1",
      case_id: "c-1",
      author_id: "alice",
      body_md: "Looks like rev **9af2**.",
      created_at: new Date().toISOString(),
    },
  ],
  total: 1,
};

beforeEach(() => {
  global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            id: "k-2",
            case_id: "c-1",
            author_id: "alice",
            body_md: "noted",
            created_at: new Date().toISOString(),
          })
        )
      );
    }
    return Promise.resolve(new Response(JSON.stringify(COMMENTS)));
  }) as unknown as typeof fetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (children: React.ReactNode) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("Comments", () => {
  it("escapes raw HTML inside renderMarkdown", () => {
    const html = renderMarkdown("<script>alert(1)</script>");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("renders bold markdown via renderMarkdown", () => {
    const html = renderMarkdown("**hi**");
    expect(html).toContain("<strong>hi</strong>");
  });

  it("loads existing comments", async () => {
    const Wrap = wrap();
    render(Wrap(<Comments caseId="c-1" />));
    await waitFor(() =>
      expect(screen.getByText(/Looks like rev/)).toBeInTheDocument()
    );
  });

  it("submits a new comment via POST", async () => {
    const Wrap = wrap();
    render(Wrap(<Comments caseId="c-1" />));
    const composer = await screen.findByTestId("comment-composer");
    const textarea = composer.querySelector("textarea") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "noted" } });
    fireEvent.submit(composer);
    await waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
      expect(
        calls.some(([, init]) => (init as RequestInit | undefined)?.method === "POST")
      ).toBe(true);
    });
  });
});
