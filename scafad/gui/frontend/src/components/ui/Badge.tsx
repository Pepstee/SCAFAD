import { ReactNode } from "react";
import { clsx } from "@/lib/format";

interface BadgeProps {
  children: ReactNode;
  tone?: "neutral" | "info" | "warn" | "danger" | "success";
  className?: string;
  /** Show animated live indicator dot */
  live?: boolean;
  /** Size variant */
  size?: "sm" | "md" | "lg";
}

const TONE_CLASSES: Record<NonNullable<BadgeProps["tone"]>, string> = {
  neutral: "bg-surface-subtle text-ink-dim border-surface-border",
  info: "bg-[rgba(91,140,255,0.12)] text-[#9ec1ff] border-[rgba(91,140,255,0.4)]",
  warn: "bg-[rgba(245,165,36,0.12)] text-[#f5d089] border-[rgba(245,165,36,0.4)]",
  danger: "bg-[rgba(255,77,77,0.12)] text-[#ffb8b8] border-[rgba(255,77,77,0.4)]",
  success: "bg-[rgba(34,197,94,0.12)] text-[#7ad9a3] border-[rgba(34,197,94,0.4)]",
};

const SIZE_CLASSES: Record<NonNullable<BadgeProps["size"]>, string> = {
  sm: "px-1.5 py-0.5 text-[10px]",
  md: "px-2 py-0.5 text-[11px]",
  lg: "px-2.5 py-1 text-xs",
};

const LIVE_DOT_TONE_COLORS: Record<NonNullable<BadgeProps["tone"]>, string> = {
  neutral: "#9aa3bd",
  info: "#9ec1ff",
  warn: "#f5d089",
  danger: "#ffb8b8",
  success: "#7ad9a3",
};

export function Badge({ children, tone = "neutral", className, live = false, size = "md" }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border font-medium uppercase tracking-wide",
        TONE_CLASSES[tone],
        SIZE_CLASSES[size],
        className
      )}
    >
      {live && (
        <span
          className="inline-block h-1.5 w-1.5 rounded-full animate-pulse-glow"
          style={{ background: LIVE_DOT_TONE_COLORS[tone] }}
          aria-hidden
        />
      )}
      {children}
    </span>
  );
}
