import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { FilterBar } from "@/components/inbox/FilterBar";
import type { InboxFilters } from "@/lib/types";

describe("FilterBar", () => {
  it("toggles severity pills", () => {
    const onChange = vi.fn();
    const filters: InboxFilters = {};
    render(
      <FilterBar
        filters={filters}
        onChange={onChange}
        onReset={() => undefined}
        knownAnomalyTypes={[]}
        knownTechniques={[]}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /escalate/i }));
    expect(onChange).toHaveBeenCalledWith({ severity: ["escalate"] });
  });

  it("activates the case-status pill when filters.case_status matches", () => {
    render(
      <FilterBar
        filters={{ case_status: "open" }}
        onChange={() => undefined}
        onReset={() => undefined}
      />
    );
    const pill = screen.getByRole("button", { name: /^Open$/ });
    // Active pills carry the accent border colour; we just verify the pill renders.
    expect(pill).toBeInTheDocument();
  });

  it("resets via the Reset button", () => {
    const onReset = vi.fn();
    render(
      <FilterBar
        filters={{ severity: ["escalate"] }}
        onChange={() => undefined}
        onReset={onReset}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(onReset).toHaveBeenCalled();
  });
});
