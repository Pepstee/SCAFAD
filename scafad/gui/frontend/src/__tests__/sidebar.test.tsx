import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { Sidebar } from "@/components/shell/Sidebar";

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 50 }))
  ) as unknown as typeof fetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderSidebar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Sidebar", () => {
  it("renders all 8 navigation entries", () => {
    renderSidebar();
    for (const label of [
      "Operations",
      "Inbox",
      "Cases",
      "Functions",
      "Threat Map",
      "System Status",
      "Settings",
      "Audit",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("marks non-Phase-2 entries with the Soon badge (Inbox + Cases drop the badge)", () => {
    renderSidebar();
    const soonBadges = screen.getAllByText(/Soon/i);
    // Phase 1 had 7 (everything except Operations).  Phase 2 has 5
    // (Functions, Threat Map, System Status, Settings, Audit).
    expect(soonBadges.length).toBe(5);
  });

  it("shows the SCAFAD wordmark", () => {
    renderSidebar();
    expect(screen.getByText("SCAFAD")).toBeInTheDocument();
    expect(screen.getByText(/Analyst Console/i)).toBeInTheDocument();
  });
});
