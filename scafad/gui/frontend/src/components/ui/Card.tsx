import { ReactNode } from "react";
import { clsx } from "@/lib/format";

interface CardProps {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  actions?: ReactNode;
  description?: ReactNode;
  /** Add severity-colored glow effect */
  glow?: "observe" | "review" | "escalate";
  /** Show loading shimmer overlay */
  loading?: boolean;
}

export function Card({ children, className, title, actions, description, glow, loading }: CardProps) {
  const glowClasses = glow ? `anim-pulse-${glow === "observe" ? "blue" : glow === "review" ? "amber" : "red"}` : "";

  return (
    <section
      className={clsx(
        "rounded-lg border border-surface-border bg-surface-panel shadow-panel",
        "transition-all duration-150 hover:-translate-y-0.5 hover:shadow-lg",
        glowClasses,
        className
      )}
    >
      {(title || actions) && (
        <header className="flex items-center justify-between gap-4 border-b border-surface-border px-5 py-3">
          <div>
            {title && <h2 className="text-sm font-semibold tracking-wide text-ink">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-surface-muted">{description}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className="relative px-5 py-4">
        {children}
        {loading && (
          <div className="absolute inset-0 rounded-lg bg-gradient-to-r from-transparent via-white to-transparent opacity-20 animate-pulse" />
        )}
      </div>
    </section>
  );
}
