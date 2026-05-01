import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import Dashboard from "@/pages/Dashboard";

vi.mock("recharts", async () => {
  const actual: any = await vi.importActual("recharts");
  // ResponsiveContainer hangs in jsdom because it polls a non-existent layout;
  // replace it with a passthrough wrapper for smoke tests.
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 400, height: 200 }}>{children}</div>
    ),
  };
});

const SUMMARY = {
  open_count: 12,
  severity_mix: { observe: 30, review: 8, escalate: 4 },
  ingest_rate_1h: 17,
  layer_p95_ms: 42.5,
  hist24h: Array.from({ length: 24 }, (_, i) => ({
    hour: new Date(Date.now() - (23 - i) * 3600_000).toISOString(),
    observe: i,
    review: i % 3,
    escalate: i % 5 === 0 ? 1 : 0,
  })),
};

const FEED = {
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
  ],
  total: 1,
  page: 1,
  page_size: 10,
};

beforeEach(() => {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/api/detections/summary")) {
      return Promise.resolve(new Response(JSON.stringify(SUMMARY)));
    }
    if (url.includes("/api/detections")) {
      return Promise.resolve(new Response(JSON.stringify(FEED)));
    }
    return Promise.reject(new Error(`unexpected fetch: ${url}`));
  }) as unknown as typeof fetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Dashboard smoke", () => {
  it("renders the page heading", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>
    );
    expect(await screen.findByText("Operations Dashboard")).toBeInTheDocument();
  });

  it("renders the four KPI tiles when summary loads", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByText(/Open detections/i)).toBeInTheDocument());
    expect(screen.getByText(/Severity mix/i)).toBeInTheDocument();
    expect(screen.getByText(/Last 1h ingest/i)).toBeInTheDocument();
    expect(screen.getByText(/Layer p95 latency/i)).toBeInTheDocument();
  });

  it("renders the live detection feed once fetched", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByText("Live detection feed")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("demo_fn")).toBeInTheDocument());
  });

  it("renders the 24h severity histogram card", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>
    );
    expect(await screen.findByText(/24-hour severity histogram/i)).toBeInTheDocument();
  });
});
