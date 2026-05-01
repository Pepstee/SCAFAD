import { describe, expect, it } from "vitest";

import {
  formatBytes,
  formatRelativeTime,
  formatSeverity,
  formatTimestamp,
  severityColorVar,
} from "@/lib/format";

describe("format helpers", () => {
  it("formats severity labels", () => {
    expect(formatSeverity("observe")).toBe("Observe");
    expect(formatSeverity("review")).toBe("Review");
    expect(formatSeverity("escalate")).toBe("Escalate");
  });

  it("returns CSS variable for each severity", () => {
    expect(severityColorVar("observe")).toBe("var(--sev-observe)");
    expect(severityColorVar("review")).toBe("var(--sev-review)");
    expect(severityColorVar("escalate")).toBe("var(--sev-escalate)");
    expect(severityColorVar("anything")).toBe("var(--sev-info)");
  });

  it("returns em-dash for missing timestamps", () => {
    expect(formatTimestamp(null)).toBe("—");
    expect(formatRelativeTime(null)).toBe("—");
  });

  it("formats bytes with binary suffixes", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(2048)).toMatch(/KB/);
    expect(formatBytes(5 * 1024 * 1024)).toMatch(/MB/);
  });
});
