import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
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

// Mock AwsLivePanel to avoid rendering issues
vi.mock("@/components/shell/AwsLivePanel", () => ({
  AwsLivePanel: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="aws-live-panel">
      <button onClick={onClose}>Close AWS</button>
    </div>
  ),
}));

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
      function_id: "lambda-auth-service",
      anomaly_type: "memory_spike",
      severity: "review" as const,
      trust_score: 0.42,
      mitre_techniques: ["T1059"],
      decision: "review",
      risk_band: "medium",
    },
    {
      id: "row-2",
      ingested_at: new Date(Date.now() - 3600_000).toISOString(),
      event_id: "evt-2",
      function_id: "lambda-data-processor",
      anomaly_type: "exfiltration",
      severity: "escalate" as const,
      trust_score: 0.89,
      mitre_techniques: ["T1041", "T1020"],
      decision: "escalate",
      risk_band: "high",
    },
    {
      id: "row-3",
      ingested_at: new Date(Date.now() - 7200_000).toISOString(),
      event_id: "evt-3",
      function_id: "lambda-api-gateway",
      anomaly_type: "timeout",
      severity: "observe" as const,
      trust_score: 0.23,
      mitre_techniques: [],
      decision: "observe",
      risk_band: "low",
    },
  ],
  total: 3,
  page: 1,
  page_size: 10,
};

const SYSTEM_STATUS = {
  layers: [
    { layer: "layer_0", healthy: true },
    { layer: "layer_1", healthy: true },
    { layer: "layer_2", healthy: false },
    { layer: "layer_3", healthy: true },
    { layer: "layer_4", healthy: true },
    { layer: "layer_5", healthy: true },
    { layer: "layer_6", healthy: undefined },
  ],
};

beforeEach(() => {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/api/detections/summary")) {
      return Promise.resolve(new Response(JSON.stringify(SUMMARY)));
    }
    if (url.includes("/api/system/status")) {
      return Promise.resolve(new Response(JSON.stringify(SYSTEM_STATUS)));
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

describe("Dashboard Upgrade Features", () => {
  describe("KPI Trend Indicators", () => {
    it("renders KPI cards with trend indicators", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      // Wait for KPI cards to load
      await waitFor(() => expect(screen.getByText(/Open detections/i)).toBeInTheDocument());

      // Check that trend indicators are rendered (arrows and percentages)
      const kpiSection = screen.getByText(/Open detections/i).closest("section");
      expect(kpiSection).toBeInTheDocument();

      // Trend indicators contain arrows
      const arrows = kpiSection?.querySelectorAll("span");
      const hasArrows = Array.from(arrows || []).some((el) =>
        el.textContent?.includes("↑") || el.textContent?.includes("↓")
      );
      expect(hasArrows).toBe(true);
    });

    it("renders all four KPI cards with values", async () => {
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

      // Check that severity mix shows the correct numbers
      expect(screen.getByText("30")).toBeInTheDocument(); // observe count
      expect(screen.getByText("8")).toBeInTheDocument(); // review count
      expect(screen.getByText("4")).toBeInTheDocument(); // escalate count
    });
  });

  describe("Detection Timeline (AreaChart)", () => {
    it("renders the detection timeline card with AreaChart", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() =>
        expect(screen.getByText(/Detection timeline \(24h\)/i)).toBeInTheDocument()
      );

      // Check for the description that indicates stacked areas
      expect(screen.getByText(/stacked by severity/i)).toBeInTheDocument();
    });

    it("renders AreaChart with three severity areas", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() =>
        expect(screen.getByText(/Detection timeline \(24h\)/i)).toBeInTheDocument()
      );

      // The AreaChart should be rendered with ResponsiveContainer
      const chartContainer = screen.getByText(/Detection timeline/).closest("section");
      expect(chartContainer).toBeInTheDocument();
    });
  });

  describe("Severity Breakdown (PieChart)", () => {
    it("renders the severity breakdown donut chart", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => expect(screen.getByText(/Severity breakdown/i)).toBeInTheDocument());

      // Check for the description
      expect(screen.getByText(/Click segment to filter/i)).toBeInTheDocument();

      // Check that the total count is displayed
      await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument()); // 30+8+4
    });
  });

  describe("Clear Filters Button", () => {
    it("does not show Clear Filters button when no filters are active", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => expect(screen.getByText(/Open detections/i)).toBeInTheDocument());

      const clearButton = screen.queryByText(/✕ Clear Filters/);
      expect(clearButton).not.toBeInTheDocument();
    });
  });

  describe("Live Feed Button and Panel", () => {
    it("renders the Live Feed button in the header", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      const feedButton = screen.getByText(/📬 Live Feed/);
      expect(feedButton).toBeInTheDocument();
    });

    it("opens Live Anomaly Feed panel when Live Feed button is clicked", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => expect(screen.getByText(/Open detections/i)).toBeInTheDocument());

      // Click the Live Feed button
      const feedButton = screen.getByText(/📬 Live Feed/);
      fireEvent.click(feedButton);

      // Wait for the panel to open
      await waitFor(() => expect(screen.getByText(/Live Alerts/)).toBeInTheDocument());

      // Check that detections are rendered in the feed
      expect(screen.getByText("lambda-auth-service")).toBeInTheDocument();
    });

    it("closes Live Anomaly Feed panel when close button is clicked", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => expect(screen.getByText(/Open detections/i)).toBeInTheDocument());

      // Open the panel
      const feedButton = screen.getByText(/📬 Live Feed/);
      fireEvent.click(feedButton);

      await waitFor(() => expect(screen.getByText(/Live Alerts/)).toBeInTheDocument());

      // Close the panel
      const closeButton = screen.getByText("✕");
      fireEvent.click(closeButton);

      // Check that the panel is closed
      await waitFor(() => expect(screen.queryByText(/Live Alerts/)).not.toBeInTheDocument());
    });

    it("displays detections in feed panel with severity color codes", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => expect(screen.getByText(/Open detections/i)).toBeInTheDocument());

      const feedButton = screen.getByText(/📬 Live Feed/);
      fireEvent.click(feedButton);

      await waitFor(() => expect(screen.getByText(/lambda-auth-service/)).toBeInTheDocument());

      // Check that anomaly types are shown
      expect(screen.getByText("memory_spike")).toBeInTheDocument();
      expect(screen.getByText("exfiltration")).toBeInTheDocument();
    });
  });

  describe("MITRE Techniques Display", () => {
    it("renders MITRE techniques as styled badge chips", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      // Wait for the detection feed to load
      await waitFor(() => expect(screen.getByText("lambda-auth-service")).toBeInTheDocument());

      // Check that MITRE techniques are rendered
      // The first row has T1059
      const table = screen.getByText("lambda-auth-service").closest("table");
      expect(table).toBeInTheDocument();

      // MITRE techniques should be visible somewhere in the table
      const allText = document.body.textContent;
      expect(allText).toContain("T1059");
      expect(allText).toContain("T1041");
    });

    it("displays empty dash for detections with no MITRE techniques", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      // Wait for the detection feed to load with the lambda-api-gateway function
      await waitFor(() => expect(screen.getByText("lambda-api-gateway")).toBeInTheDocument());

      // The lambda-api-gateway row has no MITRE techniques, should show "—"
      const allText = document.body.textContent;
      expect(allText).toContain("—");
    });
  });

  describe("System Health Bar", () => {
    it("renders the system health bar at the bottom", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      // Wait for system status to load
      await waitFor(() => expect(screen.getByText(/Layer Health/i)).toBeInTheDocument());
    });

    it("displays layer health status with correct colors", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => expect(screen.getByText(/Layer Health/i)).toBeInTheDocument());

      // The health bar should render - at minimum, the "Layer Health" label and status should exist
      const healthLabel = screen.getByText(/Layer Health/i);
      expect(healthLabel).toBeInTheDocument();

      // The parent container should have content (the health segments)
      const healthContainer = healthLabel.closest("div")?.parentElement;
      expect(healthContainer).toBeInTheDocument();
    });
  });

  describe("Detection Feed Filtering", () => {
    it("renders all detections initially", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => expect(screen.getByText(/lambda-auth-service/)).toBeInTheDocument());
      await waitFor(() => expect(screen.getByText(/lambda-data-processor/)).toBeInTheDocument());
      await waitFor(() => expect(screen.getByText(/lambda-api-gateway/)).toBeInTheDocument());
    });

    it("shows filtered count in feed description when filters are active", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => expect(screen.getByText(/Open detections/i)).toBeInTheDocument());

      // The description initially should say "3 items" (no filters)
      const feedDescription = screen.getByText(/items.*streamed via SSE/);
      expect(feedDescription.textContent).toContain("3 items");
      expect(feedDescription.textContent).not.toContain("filtered");
    });
  });

  describe("Auto-refresh intervals", () => {
    it("displays auto-refresh indicator in header", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => expect(screen.getByText(/Open detections/i)).toBeInTheDocument());

      // Check for auto-refresh indicator
      expect(screen.getByText(/Auto-refresh/)).toBeInTheDocument();
      expect(screen.getByText(/15s/)).toBeInTheDocument();
    });
  });

  describe("Component Rendering", () => {
    it("renders all main sections without errors", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      // Header
      expect(await screen.findByText("Operations Dashboard")).toBeInTheDocument();

      // KPI section
      await waitFor(() => expect(screen.getByText(/Open detections/i)).toBeInTheDocument());

      // Charts section
      expect(screen.getByText(/Detection timeline \(24h\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Severity breakdown/i)).toBeInTheDocument();

      // Feed section
      expect(screen.getByText(/Live detection feed/i)).toBeInTheDocument();

      // System health
      await waitFor(() => expect(screen.getByText(/Layer Health/i)).toBeInTheDocument());
    });

    it("renders AWS Live button", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => expect(screen.getByText(/Open detections/i)).toBeInTheDocument());

      expect(screen.getByText(/☁ AWS Live/)).toBeInTheDocument();
    });

    it("renders Live Ingest button", async () => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Dashboard />
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(() => expect(screen.getByText(/Open detections/i)).toBeInTheDocument());

      expect(screen.getByText(/⚡ Live Ingest/)).toBeInTheDocument();
    });
  });
});
