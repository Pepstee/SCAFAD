import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import Inbox from "@/pages/Inbox";

const SUMMARY = {
  total: 3,
  severity_counts: { observe: 1, review: 1, escalate: 1 },
  case_status_counts: { open: 0, triage: 0, contained: 0, closed: 0, none: 3 },
  top_mitre: [{ technique: "T1059", count: 2 }],
};

const DETECTIONS = {
  items: [
    {
      id: "row-1",
      ingested_at: new Date().toISOString(),
      event_id: "evt-1",
      function_id: "demo_fn",
      anomaly_type: "memory_spike",
      severity: "review" as const,
      trust_score: 0.42,
      mitre_techniques: ["T1059"],
      decision: "review",
      risk_band: "medium",
    },
    {
      id: "row-2",
      ingested_at: new Date().toISOString(),
      event_id: "evt-2",
      function_id: "checkout_api",
      anomaly_type: "cpu_burst",
      severity: "escalate" as const,
      trust_score: 0.88,
      mitre_techniques: ["T1499"],
      decision: "escalate",
      risk_band: "high",
    },
  ],
  total: 2,
  page: 1,
  page_size: 50,
};

const CASES = { items: [], total: 0, page: 1, page_size: 50 };
const VIEWS = { items: [], total: 0 };

beforeEach(() => {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/api/inbox/summary")) {
      return Promise.resolve(new Response(JSON.stringify(SUMMARY)));
    }
    if (url.includes("/api/cases")) {
      return Promise.resolve(new Response(JSON.stringify(CASES)));
    }
    if (url.includes("/api/views")) {
      return Promise.resolve(new Response(JSON.stringify(VIEWS)));
    }
    if (url.includes("/api/detections")) {
      return Promise.resolve(new Response(JSON.stringify(DETECTIONS)));
    }
    return Promise.reject(new Error(`unexpected fetch: ${url}`));
  }) as unknown as typeof fetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Inbox />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Inbox smoke", () => {
  it("renders the Detection Inbox heading", async () => {
    renderPage();
    expect(await screen.findByText("Detection Inbox")).toBeInTheDocument();
  });

  it("renders the filter bar", async () => {
    renderPage();
    expect(await screen.findByTestId("inbox-filter-bar")).toBeInTheDocument();
  });

  it("renders the inbox table after data loads", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId("inbox-table")).toBeInTheDocument());
    expect(await screen.findByText("demo_fn")).toBeInTheDocument();
    expect(await screen.findByText("checkout_api")).toBeInTheDocument();
  });

  it("renders summary tiles with the severity counts", async () => {
    renderPage();
    // Wait for at least one occurrence; the SeverityChip + tile labels both
    // contain these strings, so we just assert presence rather than uniqueness.
    expect((await screen.findAllByText(/Observe/)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/Review/)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/Escalate/)).length).toBeGreaterThan(0);
  });
});
