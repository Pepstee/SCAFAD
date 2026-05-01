import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { CaseDrawer } from "@/components/cases/CaseDrawer";

const CASE = {
  id: "c-1",
  title: "Memory leak",
  status: "open",
  severity_rollup: "review",
  assignee_id: null,
  opened_at: new Date().toISOString(),
  closed_at: null,
  created_by: "analyst@scafad.local",
  version: 3,
  detection_count: 5,
};

beforeEach(() => {
  global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (init?.method === "PATCH") {
      return Promise.resolve(new Response(JSON.stringify({ ...CASE, version: CASE.version + 1, status: "triage" })));
    }
    if (url.includes("/api/cases/c-1/events")) {
      return Promise.resolve(new Response(JSON.stringify({ items: [], total: 0 })));
    }
    if (url.includes("/api/cases/c-1/comments")) {
      return Promise.resolve(new Response(JSON.stringify({ items: [], total: 0 })));
    }
    if (url.includes("/api/cases/c-1/detections")) {
      return Promise.resolve(new Response(JSON.stringify({ items: [], total: 0 })));
    }
    if (url.includes("/api/cases/c-1")) {
      return Promise.resolve(new Response(JSON.stringify(CASE)));
    }
    return Promise.reject(new Error(`unexpected fetch: ${url}`));
  }) as unknown as typeof fetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderDrawer() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CaseDrawer caseId="c-1" open onClose={() => undefined} />
    </QueryClientProvider>
  );
}

describe("CaseDrawer", () => {
  it("renders the drawer when open with a caseId", async () => {
    renderDrawer();
    expect(await screen.findByTestId("case-drawer")).toBeInTheDocument();
  });

  it("loads the case title", async () => {
    renderDrawer();
    expect(await screen.findByText("Memory leak")).toBeInTheDocument();
  });

  it("renders the four tabs", async () => {
    renderDrawer();
    const tabs = await screen.findByTestId("case-drawer-tabs");
    expect(tabs).toHaveTextContent("Overview");
    expect(tabs).toHaveTextContent("Detections");
    expect(tabs).toHaveTextContent("Comments");
    expect(tabs).toHaveTextContent("Lifecycle");
  });

  it("issues a PATCH with expected_version when the state is changed", async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText("Memory leak")).toBeInTheDocument());
    const select = screen.getByLabelText("Case state") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "triage" } });
    await waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
      const patch = calls.find(([, init]) => (init as RequestInit | undefined)?.method === "PATCH");
      expect(patch).toBeDefined();
      const body = JSON.parse(((patch as [string, RequestInit])[1].body as string) || "{}");
      expect(body.expected_version).toBe(3);
      expect(body.status).toBe("triage");
    });
  });
});
