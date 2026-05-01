import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { SeverityChip } from "@/components/ui/SeverityChip";
import { formatSeverity, severityColorVar } from "@/lib/format";

describe("SeverityChip", () => {
  it("renders the canonical label for each severity", () => {
    for (const sev of ["observe", "review", "escalate"] as const) {
      render(<SeverityChip severity={sev} />);
      expect(screen.getByText(formatSeverity(sev))).toBeInTheDocument();
    }
  });

  it("uses the matching CSS variable for the border colour", () => {
    render(<SeverityChip severity="escalate" />);
    const chip = screen.getByTestId("severity-chip-escalate") as HTMLElement;
    // jsdom does not resolve CSS variables in computed styles, so we read the
    // inline style attribute directly rather than going via toHaveStyle.
    expect(chip.style.borderColor).toBe(severityColorVar("escalate"));
  });

  it("falls back to info colour for an unknown severity", () => {
    render(<SeverityChip severity={"weird" as never} />);
    const chip = screen.getByTestId("severity-chip-weird") as HTMLElement;
    expect(chip.style.color).toBe(severityColorVar("weird"));
  });
});
