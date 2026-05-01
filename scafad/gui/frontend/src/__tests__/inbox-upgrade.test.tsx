import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import Inbox from "@/pages/Inbox";

// ============================================================================
// Test Data
// ============================================================================

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
      ingested_at: "2026-05-01T10:00:00Z",
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
      ingested_at: "2026-05-01T11:00:00Z",
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

const DETECTION_DETAIL = {
  id: "row-1",
  ingested_at: "2026-05-01T10:00:00Z",
  event_id: "evt-1",
  function_id: "demo_fn",
  anomaly_type: "memory_spike",
  severity: "review" as const,
  trust_score: 0.42,
  mitre_techniques: ["T1059"],
  decision: "review",
  risk_band: "medium",
  layer_payload: {
    layer0: { detectors: ["detector_a", "detector_b"] },
    layer1: { redacted: true },
    layer2: { score: 0.42 },
  },
};

const CASES = { items: [], total: 0, page: 1, page_size: 50 };
const VIEWS = { items: [], total: 0 };

// ============================================================================
// Test Setup
// ============================================================================

beforeEach(() => {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/api/inbox/summary")) {
      return Promise.resolve(new Response(JSON.stringify(SUMMARY)));
    }
    if (url.includes("/api/detections") && url.includes("row-1")) {
      return Promise.resolve(new Response(JSON.stringify(DETECTION_DETAIL)));
    }
    if (url.includes("/api/detections") && !url.includes("row-")) {
      return Promise.resolve(new Response(JSON.stringify(DETECTIONS)));
    }
    if (url.includes("/api/cases")) {
      return Promise.resolve(new Response(JSON.stringify(CASES)));
    }
    if (url.includes("/api/views")) {
      return Promise.resolve(new Response(JSON.stringify(VIEWS)));
    }
    return Promise.reject(new Error(`unexpected fetch: ${url}`));
  }) as unknown as typeof fetch;

  global.prompt = vi.fn().mockReturnValue("Test Case Title");
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ============================================================================
// Helper Functions
// ============================================================================

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/?severity=review"]}>
        <Inbox />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function renderPageWithSelected(selectedId: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/?selected=${selectedId}`]}>
        <Inbox />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ============================================================================
// Test Suites
// ============================================================================

describe("Inbox Page Upgrade - Core Features", () => {
  it("renders Detection Inbox page with split-pane layout", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Detection Inbox")).toBeInTheDocument());

    // Verify layout components are present
    expect(screen.getByTitle("Drag to resize")).toBeInTheDocument(); // Divider
    expect(screen.getByTitle("Press ? for shortcuts")).toBeInTheDocument(); // Help button
  });

  it("loads detections into table", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("demo_fn")).toBeInTheDocument();
    });

    expect(screen.getByText("checkout_api")).toBeInTheDocument();
  });


  it("loads detection detail when selected via URL parameter", async () => {
    renderPageWithSelected("row-1");

    await waitFor(() => {
      expect(screen.getByText("row-1")).toBeInTheDocument();
    });

    // Verify preview panel content is shown
    expect(screen.getByText("Detection ID")).toBeInTheDocument();
    expect(screen.getByText("Anomaly Score")).toBeInTheDocument();
  });
});

describe("Inbox Page Upgrade - Keyboard Navigation", () => {
  it("processes keyboard events without errors", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Detection Inbox")).toBeInTheDocument());

    // Fire various keyboard events
    fireEvent.keyDown(window, { key: "j" });
    fireEvent.keyDown(window, { key: "k" });
    fireEvent.keyDown(window, { key: "?" });
    fireEvent.keyDown(window, { key: "Escape" });

    // Page should still be functional
    expect(screen.getByText("Detection Inbox")).toBeInTheDocument();
  });

  it("shows keyboard legend when Help button is clicked", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Detection Inbox")).toBeInTheDocument());

    const helpButton = screen.getByTitle("Press ? for shortcuts");
    fireEvent.click(helpButton);

    await waitFor(() => {
      expect(screen.getByText("Keyboard Shortcuts")).toBeInTheDocument();
    });
  });

  it("displays all keyboard shortcuts in legend", async () => {
    renderPage();
    const helpButton = screen.getByTitle("Press ? for shortcuts");
    fireEvent.click(helpButton);

    await waitFor(() => {
      expect(screen.getByText("Keyboard Shortcuts")).toBeInTheDocument();
    });

    // Verify shortcuts are listed
    expect(screen.getByText("Move selection up/down")).toBeInTheDocument();
    expect(screen.getByText("Toggle this legend")).toBeInTheDocument();
  });
});

describe("Inbox Page Upgrade - Preview Panel", () => {
  it("displays preview panel components when detection selected", async () => {
    renderPageWithSelected("row-1");

    await waitFor(() => {
      expect(screen.getByText("Detection ID")).toBeInTheDocument();
    });

    // Verify key preview components
    expect(screen.getByText("Anomaly Score")).toBeInTheDocument();
    expect(screen.getByText("0.420")).toBeInTheDocument(); // Trust score displayed
  });

  it("shows action buttons in preview panel", async () => {
    renderPageWithSelected("row-1");

    await waitFor(() => {
      expect(screen.getByText("Open Case")).toBeInTheDocument();
    });

    expect(screen.getByText("Dismiss")).toBeInTheDocument();
  });

  it("has close button in preview panel", async () => {
    renderPageWithSelected("row-1");

    await waitFor(() => {
      expect(screen.getByText("Detection ID")).toBeInTheDocument();
    });

    const closeButton = screen.getByTitle("Close preview (Esc)");
    expect(closeButton).toBeInTheDocument();
  });
});

describe("Inbox Page Upgrade - Resizable Divider", () => {
  it("renders resizable divider with correct styling", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Detection Inbox")).toBeInTheDocument());

    const divider = screen.getByTitle("Drag to resize");
    expect(divider).toBeInTheDocument();
    expect(divider).toHaveClass("cursor-col-resize");
  });

  it("divider responds to mouse events", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Detection Inbox")).toBeInTheDocument());

    const divider = screen.getByTitle("Drag to resize");

    // Simulate mouse down on divider
    fireEvent.mouseDown(divider);

    // Divider should still be in document
    expect(screen.getByTitle("Drag to resize")).toBeInTheDocument();
  });
});

describe("Inbox Page Upgrade - Bulk Actions", () => {
  it("bulk toolbar is hidden initially", async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText("demo_fn")).toBeInTheDocument());

    // Initially bulk toolbar should not be visible
    expect(screen.queryByTestId("bulk-toolbar")).not.toBeInTheDocument();
  });
});

describe("Inbox Page Upgrade - Existing Functionality", () => {
  it("preserves filter bar", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Detection Inbox")).toBeInTheDocument());

    expect(screen.getByTestId("inbox-filter-bar")).toBeInTheDocument();
  });

  it("preserves summary tiles", async () => {
    renderPage();

    // Wait for summary to load
    expect((await screen.findAllByText(/Observe|Review|Escalate/)).length).toBeGreaterThan(0);
  });

  it("preserves detection table rendering", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("demo_fn")).toBeInTheDocument();
    });

    // Table should contain expected detections
    expect(screen.getByText("checkout_api")).toBeInTheDocument();
  });

  it("maintains page functionality with interactions", async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText("demo_fn")).toBeInTheDocument());

    // Select a row
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]);

    // Page should remain functional
    expect(screen.getByText("Detection Inbox")).toBeInTheDocument();
  });
});

describe("Inbox Page Upgrade - Smoke Tests", () => {
  it("page renders without errors", async () => {
    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText("Detection Inbox")).toBeInTheDocument();
    });

    // Verify no error elements in DOM
    expect(container.querySelector("[class*='error']")).toBeNull();
  });

  it("all required UI elements are present", async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText("Detection Inbox")).toBeInTheDocument());

    // Header
    expect(screen.getByText("Detection Inbox")).toBeInTheDocument();

    // Filter bar
    expect(screen.getByTestId("inbox-filter-bar")).toBeInTheDocument();

    // Help button
    expect(screen.getByTitle("Press ? for shortcuts")).toBeInTheDocument();

    // Divider
    expect(screen.getByTitle("Drag to resize")).toBeInTheDocument();
  });

  it("can interact with detections list", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("demo_fn")).toBeInTheDocument();
    });

    // Verify all test detections are rendered
    expect(screen.getByText("checkout_api")).toBeInTheDocument();

    // Checkboxes exist for selection
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBeGreaterThan(0);
  });
});
