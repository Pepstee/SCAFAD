import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { BulkToolbar } from "@/components/inbox/BulkToolbar";

describe("BulkToolbar", () => {
  it("does not render when selection is empty", () => {
    const { container } = render(
      <BulkToolbar
        selectedCount={0}
        onAction={() => undefined}
        onClearSelection={() => undefined}
        exportHref="/api/inbox/export.csv"
      />
    );
    expect(container.querySelector('[data-testid="bulk-toolbar"]')).toBeNull();
  });

  it("renders the toolbar when ≥1 row is selected", () => {
    render(
      <BulkToolbar
        selectedCount={3}
        onAction={() => undefined}
        onClearSelection={() => undefined}
        exportHref="/api/inbox/export.csv"
      />
    );
    expect(screen.getByTestId("bulk-toolbar")).toBeInTheDocument();
    expect(screen.getByText("3 selected")).toBeInTheDocument();
  });

  it("calls onAction with assign payload", () => {
    const onAction = vi.fn();
    render(
      <BulkToolbar
        selectedCount={2}
        onAction={onAction}
        onClearSelection={() => undefined}
        exportHref="/api/inbox/export.csv"
      />
    );
    fireEvent.click(screen.getByText("Assign to me"));
    expect(onAction).toHaveBeenCalledWith("assign", expect.objectContaining({ assignee_id: expect.any(String) }));
  });

  it("renders an export anchor with the supplied href", () => {
    render(
      <BulkToolbar
        selectedCount={1}
        onAction={() => undefined}
        onClearSelection={() => undefined}
        exportHref="/api/inbox/export.csv?severity=escalate"
      />
    );
    const link = screen.getByText("Export CSV") as HTMLAnchorElement;
    expect(link.getAttribute("href")).toContain("severity=escalate");
  });
});
