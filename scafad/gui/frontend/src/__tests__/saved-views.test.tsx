import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { SavedViews } from "@/components/inbox/SavedViews";

const VIEW = {
  id: "v-1",
  name: "Critical only",
  owner_id: "analyst@scafad.local",
  filter_json: { severity: ["escalate"] },
  sort_json: [],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  pinned: true,
};

const VIEWS_LIST = { items: [VIEW], total: 1 };

beforeEach(() => {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/api/views") && (!url.includes("DELETE"))) {
      return Promise.resolve(new Response(JSON.stringify(VIEWS_LIST)));
    }
    return Promise.resolve(new Response(JSON.stringify({})));
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

describe("SavedViews", () => {
  it("renders the saved-views trigger", async () => {
    const Wrap = wrap();
    render(Wrap(<SavedViews filters={{}} onApply={() => undefined} />));
    expect(await screen.findByText(/Saved views/)).toBeInTheDocument();
  });

  it("opens the menu and lists existing views", async () => {
    const Wrap = wrap();
    render(Wrap(<SavedViews filters={{}} onApply={() => undefined} />));
    fireEvent.click(await screen.findByText(/Saved views/));
    await waitFor(() => expect(screen.getByText(/Critical only/)).toBeInTheDocument());
  });

  it("calls onApply when a view is clicked", async () => {
    const Wrap = wrap();
    const onApply = vi.fn();
    render(Wrap(<SavedViews filters={{}} onApply={onApply} />));
    fireEvent.click(await screen.findByText(/Saved views/));
    fireEvent.click(await screen.findByText(/Critical only/));
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ id: "v-1" }));
  });
});
