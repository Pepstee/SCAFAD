import { Severity } from "@/lib/types";
import { formatSeverity, severityColorVar, clsx } from "@/lib/format";

interface SeverityChipProps {
  severity: Severity | string;
  className?: string;
  compact?: boolean;
  /** Add animated glow effect for escalate severity */
  glow?: boolean;
}

export function SeverityChip({ severity, className, compact, glow }: SeverityChipProps) {
  const color = severityColorVar(severity);
  const isEscalate = severity === "escalate" || severity === "Escalate";
  const glowAnimation = glow && isEscalate ? "animate-glow-pulse-escalate" : "";

  return (
    <span
      data-testid={`severity-chip-${severity}`}
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border bg-surface-subtle font-medium transition-shadow duration-200",
        compact ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
        glowAnimation,
        className
      )}
      style={{ borderColor: color, color }}
    >
      <span
        aria-hidden
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: color }}
      />
      {formatSeverity(severity)}
    </span>
  );
}
