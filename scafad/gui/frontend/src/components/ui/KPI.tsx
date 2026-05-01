import { ReactNode, useEffect, useRef, useState } from "react";
import { Card } from "./Card";

interface KPIProps {
  label: string;
  value: number | ReactNode;
  hint?: ReactNode;
  /** Trend indicator: either a ReactNode (for backward compatibility) or an object with direction and value */
  trend?: ReactNode | { direction: "up" | "down"; value: number };
  /** Array of numbers for mini sparkline (0-100 scale) */
  sparkline?: number[];
}

/**
 * Animated number counter for numeric values.
 */
function CountUpValue({ value, duration = 800 }: { value: number; duration?: number }) {
  const [displayValue, setDisplayValue] = useState(0);
  const frameRef = useRef<number>();

  useEffect(() => {
    if (typeof value !== "number") return;

    const startTime = Date.now();
    const startValue = displayValue;

    const animate = () => {
      const now = Date.now();
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);

      const newValue = Math.floor(startValue + (value - startValue) * progress);
      setDisplayValue(newValue);

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    };

    frameRef.current = requestAnimationFrame(animate);

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [value, duration]);

  return <>{displayValue}</>;
}

/**
 * Sparkline visualization (simple mini chart).
 */
function Sparkline({ data }: { data: number[] }) {
  if (!data || data.length === 0) return null;

  // Create a simple SVG sparkline
  const width = 60;
  const height = 20;
  const padding = 2;
  const pointWidth = (width - padding * 2) / (data.length - 1 || 1);

  // Normalize data to 0-height range
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((val, idx) => {
    const x = padding + idx * pointWidth;
    const y = height - padding - ((val - min) / range) * (height - padding * 2);
    return `${x},${y}`;
  });

  return (
    <svg width={width} height={height} className="mt-1" viewBox={`0 0 ${width} ${height}`}>
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        opacity="0.6"
      />
    </svg>
  );
}

export function KPI({ label, value, hint, trend, sparkline }: KPIProps) {
  // Check if trend is an object with direction/value (new format) or ReactNode (backward compat)
  const isTrendObject = trend && typeof trend === "object" && "direction" in trend && !("$$typeof" in trend);
  const trendColor = isTrendObject && (trend as any).direction === "up" ? "#22c55e" : "#ff4d4d";
  const trendArrow = isTrendObject && (trend as any).direction === "up" ? "↑" : "↓";

  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <span className="text-xs uppercase tracking-wider text-surface-muted">{label}</span>
        {trend && (
          isTrendObject ? (
            <span className="text-xs font-semibold" style={{ color: trendColor }}>
              {trendArrow} {(trend as any).value}%
            </span>
          ) : (
            <span className="text-xs font-semibold">{trend as ReactNode}</span>
          )
        )}
      </div>
      <div className="mt-2 text-3xl font-semibold tabular-nums tracking-tight text-ink">
        {typeof value === "number" ? (
          <span className="animate-count-tick">
            <CountUpValue value={value} />
          </span>
        ) : (
          value
        )}
      </div>
      {sparkline && <Sparkline data={sparkline} />}
      {hint && <div className="mt-1 text-xs text-surface-muted">{hint}</div>}
    </Card>
  );
}
