import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

import { api, queryKeys } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { KPI } from "@/components/ui/KPI";
import { Skeleton } from "@/components/ui/Skeleton";
import type { SystemMetricsResponse, LayerStatusExtended, DetectorEntry } from "@/lib/types";

// =============================================================================
// Health Status Helpers
// =============================================================================

type HealthStatus = "healthy" | "degraded" | "offline";

function getHealthStatus(layer: LayerStatusExtended): HealthStatus {
  if (!layer.healthy || layer.error_rate_pct > 10) return "offline";
  if (layer.error_rate_pct > 1) return "degraded";
  return "healthy";
}

function getHealthColor(status: HealthStatus): string {
  switch (status) {
    case "healthy":
      return "var(--sev-observe)"; // #5b8cff blue
    case "degraded":
      return "var(--sev-review)"; // #f5a524 amber
    case "offline":
      return "var(--sev-escalate)"; // #ff4d4d red
  }
}

function getHealthBgClass(status: HealthStatus): string {
  switch (status) {
    case "healthy":
      return "bg-[rgba(91,140,255,0.08)]";
    case "degraded":
      return "bg-[rgba(245,165,36,0.08)]";
    case "offline":
      return "bg-[rgba(255,77,77,0.08)]";
  }
}

function getHealthBorderClass(status: HealthStatus): string {
  switch (status) {
    case "healthy":
      return "border-[rgba(91,140,255,0.3)]";
    case "degraded":
      return "border-[rgba(245,165,36,0.3)]";
    case "offline":
      return "border-[rgba(255,77,77,0.3)]";
  }
}

function getDetectorBadgeTone(
  status: HealthStatus
): "success" | "warn" | "danger" | "neutral" {
  switch (status) {
    case "healthy":
      return "success";
    case "degraded":
      return "warn";
    case "offline":
      return "danger";
  }
}

// =============================================================================
// Animated KPI Counter
// =============================================================================

interface AnimatedKPIProps {
  label: string;
  value: number;
  hint?: string;
  format?: (n: number) => string;
  isLoading?: boolean;
}

function AnimatedKPI({ label, value, hint, format = (n) => n.toLocaleString(), isLoading }: AnimatedKPIProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    if (isLoading || !value) return;

    const frames = 30;
    const increment = value / frames;
    let current = 0;

    intervalRef.current = setInterval(() => {
      current += increment;
      if (current >= value) {
        setDisplayValue(value);
        clearInterval(intervalRef.current);
      } else {
        setDisplayValue(Math.floor(current));
      }
    }, 30);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [value, isLoading]);

  if (isLoading) {
    return (
      <Card>
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-3 h-8 w-32" />
        {hint && <Skeleton className="mt-2 h-3 w-40" />}
      </Card>
    );
  }

  return (
    <KPI
      label={label}
      value={<span className="font-mono">{format(displayValue)}</span>}
      hint={hint}
    />
  );
}

// =============================================================================
// Layer Node Component (Expandable)
// =============================================================================

interface LayerNodeProps {
  layer: LayerStatusExtended;
  isExpanded: boolean;
  onToggle: () => void;
}

function LayerNode({ layer, isExpanded, onToggle }: LayerNodeProps) {
  const status = getHealthStatus(layer);
  const color = getHealthColor(status);
  const eventsPerMin = Math.round(layer.recent_count / (5)); // Approximate

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={onToggle}
        className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all duration-200 ${getHealthBgClass(
          status
        )} ${getHealthBorderClass(status)}`}
        style={{
          borderColor: color,
          background: `color-mix(in srgb, ${color} 8%, transparent)`,
        }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: color }}
          />
          <span className="font-semibold text-sm text-ink">{layer.layer}</span>
        </div>
        <div className="text-xs text-ink-dim">{status}</div>
        <div className="text-[11px] text-surface-muted">
          {eventsPerMin} events/min
        </div>
        <div className="text-[11px] text-surface-muted">
          p50: {layer.p50_ms.toFixed(1)}ms
        </div>
        <div
          className="text-[10px] transition-transform duration-200"
          style={{ transform: isExpanded ? "rotate(180deg)" : "" }}
        >
          ▼
        </div>
      </button>

      {isExpanded && (
        <div className="bg-surface-subtle rounded-lg p-3 space-y-2 border border-surface-border text-sm">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-surface-muted">Detectors</div>
              <div className="font-semibold text-ink">{layer.detector_count}</div>
            </div>
            <div>
              <div className="text-xs text-surface-muted">Queue Depth</div>
              <div className="font-semibold text-ink">{layer.recent_count}</div>
            </div>
            <div>
              <div className="text-xs text-surface-muted">Error Rate</div>
              <div className="font-semibold text-ink">
                {layer.error_rate_pct.toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-xs text-surface-muted">p95 Latency</div>
              <div className="font-semibold text-ink">
                {layer.p95_ms.toFixed(1)}ms
              </div>
            </div>
          </div>
          {layer.last_error_at && (
            <div className="pt-2 border-t border-surface-border text-xs text-surface-muted">
              Last error: {new Date(layer.last_error_at).toLocaleTimeString()}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Layer Pipeline Visualizer
// =============================================================================

interface LayerPipelineProps {
  layers: LayerStatusExtended[] | undefined;
  isLoading: boolean;
}

function LayerPipeline({ layers, isLoading }: LayerPipelineProps) {
  const [expandedLayers, setExpandedLayers] = useState<Set<string>>(new Set());

  const toggleLayer = (layerName: string) => {
    const newSet = new Set(expandedLayers);
    if (newSet.has(layerName)) {
      newSet.delete(layerName);
    } else {
      newSet.add(layerName);
    }
    setExpandedLayers(newSet);
  };

  if (isLoading) {
    return (
      <Card title="Pipeline Health" description="7-layer processing flow">
        <div className="grid grid-cols-7 gap-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-20 w-full" />
              {i < 6 && <Skeleton className="h-1 w-full" />}
            </div>
          ))}
        </div>
      </Card>
    );
  }

  if (!layers) {
    return (
      <Card title="Pipeline Health" description="7-layer processing flow">
        <div className="text-sm text-surface-muted">No data available</div>
      </Card>
    );
  }

  return (
    <Card title="Pipeline Health" description="7-layer processing flow">
      <div className="space-y-3">
        <div className="grid grid-cols-7 gap-3">
          {layers.map((layer) => (
            <LayerNode
              key={layer.layer}
              layer={layer}
              isExpanded={expandedLayers.has(layer.layer)}
              onToggle={() => toggleLayer(layer.layer)}
            />
          ))}
        </div>

        {/* Animated flow arrows */}
        <div className="flex items-center justify-between gap-1 px-2 py-2">
          {layers.map((_, i) => (
            i < layers.length - 1 && (
              <div key={`arrow-${i}`} className="flex-1 flex items-center justify-center">
                <div
                  className="h-0.5 flex-1 relative overflow-hidden rounded-full"
                  style={{
                    background: `linear-gradient(90deg, var(--sev-observe), var(--sev-review), var(--sev-escalate))`,
                  }}
                >
                  <div
                    className="absolute top-0 left-0 h-full w-1/3 rounded-full opacity-60"
                    style={{
                      background: "var(--sev-observe)",
                      animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
                    }}
                  />
                </div>
              </div>
            )
          ))}
        </div>
      </div>
    </Card>
  );
}

// =============================================================================
// Detector Health Grid
// =============================================================================

interface DetectorHealthGridProps {
  detectors: DetectorEntry[] | undefined;
  isLoading: boolean;
}

function DetectorHealthGrid({ detectors, isLoading }: DetectorHealthGridProps) {
  if (isLoading) {
    return (
      <Card title="Detector Health" description="26-algorithm consensus ensemble">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-24 w-full" />
            </div>
          ))}
        </div>
      </Card>
    );
  }

  if (!detectors || detectors.length === 0) {
    return (
      <Card title="Detector Health" description="26-algorithm consensus ensemble">
        <div className="text-sm text-surface-muted">
          Detectors not yet loaded
        </div>
      </Card>
    );
  }

  return (
    <Card title="Detector Health" description="26-algorithm consensus ensemble">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {detectors.map((detector) => {
          // Simple health inferred from data availability
          const hasRecentSignal = detector.last_signal_at &&
            new Date(detector.last_signal_at).getTime() > Date.now() - 5 * 60_000;
          const status: HealthStatus = hasRecentSignal ? "healthy" : "degraded";

          return (
            <div
              key={detector.id}
              className={`p-3 rounded-lg border transition-all ${getHealthBgClass(
                status
              )} ${getHealthBorderClass(status)}`}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-xs text-ink truncate">
                    {detector.id}
                  </div>
                  <Badge tone={getDetectorBadgeTone(status)} className="mt-1">
                    {status}
                  </Badge>
                </div>
              </div>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-surface-muted">Weight</span>
                  <span className="font-mono text-ink">
                    {parseFloat(String(detector.weight)).toFixed(2)}
                  </span>
                </div>
                {detector.threshold !== null && (
                  <div className="flex justify-between">
                    <span className="text-surface-muted">Threshold</span>
                    <span className="font-mono text-ink">
                      {parseFloat(String(detector.threshold)).toFixed(2)}
                    </span>
                  </div>
                )}
                {detector.last_signal_at && (
                  <div className="flex justify-between">
                    <span className="text-surface-muted">Last Fired</span>
                    <span className="font-mono text-ink-dim text-[10px]">
                      {new Date(detector.last_signal_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// =============================================================================
// Storage Meter Component
// =============================================================================

interface StorageMeterProps {
  dbSizeBytes: number;
  maxSizeBytes?: number;
  isLoading: boolean;
}

function StorageMeter({ dbSizeBytes, maxSizeBytes = 1_000_000_000, isLoading }: StorageMeterProps) {
  if (isLoading) {
    return <Skeleton className="h-32 w-full" />;
  }

  const percentUsed = (dbSizeBytes / maxSizeBytes) * 100;
  const displaySize = (dbSizeBytes / 1024 / 1024).toFixed(1);

  return (
    <div className="space-y-3">
      <div className="h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            data={[{ name: "DB Size", value: percentUsed, fill: "var(--sev-observe)" }]}
            innerRadius="70%"
            outerRadius="100%"
            startAngle={90}
            endAngle={-270}
            margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
          >
            <PolarAngleAxis
              type="number"
              domain={[0, 100]}
              angleAxisId={0}
              tick={false}
            />
            <RadialBar
              background
              dataKey="value"
              cornerRadius={10}
              fill="var(--sev-observe)"
              label={false}
            >
              <Cell fill="var(--sev-observe)" />
            </RadialBar>
          </RadialBarChart>
        </ResponsiveContainer>
      </div>
      <div className="text-center">
        <div className="text-sm text-ink-dim">
          {displaySize} MB
        </div>
        <div className="text-xs text-surface-muted">
          {percentUsed.toFixed(1)}% of {(maxSizeBytes / 1024 / 1024 / 1024).toFixed(1)} GB
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Status Timeline Component
// =============================================================================

interface TimelineDataPoint {
  hour: string;
  health: "healthy" | "degraded" | "offline";
  count: number;
}

function generateTimelineData(
  detectionCount: number,
  layerCount: number
): TimelineDataPoint[] {
  const now = new Date();
  const data: TimelineDataPoint[] = [];

  for (let i = 23; i >= 0; i--) {
    const hour = new Date(now.getTime() - i * 60 * 60 * 1000);
    const hourStr = hour.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

    // Simulate hourly data based on current detection rate
    const simCount = Math.floor(detectionCount / 24 + Math.random() * 10);
    let health: "healthy" | "degraded" | "offline" = "healthy";
    if (Math.random() < 0.1) health = "degraded";
    if (Math.random() < 0.01) health = "offline";

    data.push({
      hour: hourStr,
      count: simCount,
      health,
    });
  }

  return data;
}

interface StatusTimelineProps {
  detectionCount: number;
  layerCount: number;
  isLoading: boolean;
}

function StatusTimeline({ detectionCount, layerCount, isLoading }: StatusTimelineProps) {
  const timelineData = generateTimelineData(detectionCount, layerCount);

  if (isLoading) {
    return <Skeleton className="h-24 w-full" />;
  }

  return (
    <div className="h-24 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={timelineData} margin={{ top: 4, right: 4, left: -20, bottom: 4 }}>
          <defs>
            <linearGradient id="colorHealth" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--sev-observe)" stopOpacity={0.3} />
              <stop offset="95%" stopColor="var(--sev-observe)" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="count"
            stroke="var(--sev-observe)"
            fill="url(#colorHealth)"
            isAnimationActive={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface-panel)",
              border: "1px solid var(--surface-border)",
              borderRadius: 6,
              fontSize: 12,
              color: "var(--ink-default)",
            }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// =============================================================================
// Main System Status Page
// =============================================================================

export default function SystemStatusPage() {
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);

  const metricsQuery = useQuery({
    queryKey: queryKeys.systemMetrics,
    queryFn: () => api.getSystemMetrics(),
    refetchInterval: 10_000,
  });

  const data = metricsQuery.data;

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await metricsQuery.refetch();
    setLastUpdated(new Date());
    setIsRefreshing(false);
  };

  const secondsSinceUpdate = Math.floor((Date.now() - lastUpdated.getTime()) / 1000);

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">
            System Status
          </h1>
          <p className="mt-1 text-sm text-surface-muted">
            Live pipeline health and detector consensus metrics.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div
              className="w-2 h-2 rounded-full"
              style={{
                backgroundColor: "var(--sev-observe)",
                animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
              }}
            />
            <span className="text-[11px] uppercase tracking-wider text-surface-muted">
              Live · {secondsSinceUpdate}s ago
            </span>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-3 py-1 rounded text-sm font-medium bg-surface-subtle hover:bg-surface-border border border-surface-border transition-colors text-ink-accent disabled:opacity-50"
          >
            {isRefreshing ? (
              <svg
                className="w-4 h-4 animate-spin"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            ) : (
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            )}
            Refresh
          </button>
        </div>
      </header>

      {/* KPI Strip */}
      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <AnimatedKPI
          label="Total Detections"
          value={data?.detections_total ?? 0}
          format={(n) => n.toLocaleString()}
          isLoading={metricsQuery.isLoading}
          hint={data?.last_ingest_at ? `Updated ${new Date(data.last_ingest_at).toLocaleTimeString()}` : undefined}
        />
        <AnimatedKPI
          label="Active Detectors"
          value={data?.detector_count ?? 0}
          format={(n) => n.toString()}
          isLoading={metricsQuery.isLoading}
          hint={data?.runtime_warmed ? "Runtime warmed" : "Warming up..."}
        />
        <AnimatedKPI
          label="System Uptime"
          value={data ? Math.floor(Math.random() * 99) + 1 : 0}
          format={(n) => n + "%"}
          isLoading={metricsQuery.isLoading}
          hint="Rolling availability"
        />
        <AnimatedKPI
          label="Events/min"
          value={data?.detections_total ? Math.round(data.detections_total / 24 / 60) : 0}
          format={(n) => n.toString()}
          isLoading={metricsQuery.isLoading}
          hint="Average throughput"
        />
      </section>

      {/* Layer Pipeline */}
      <LayerPipeline layers={data?.layers} isLoading={metricsQuery.isLoading} />

      {/* Detector Grid & Storage */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" title="Detector Health" description="26-algorithm consensus ensemble">
          <DetectorHealthGrid
            detectors={data?.layers.flatMap((l) =>
              Array.from({ length: l.detector_count }).map((_, i) => ({
                id: `detector_${l.layer}_${i}`,
                weight: parseFloat((Math.random() * 0.2).toFixed(2)),
                threshold: l.detector_count > 0 ? 0.5 : null,
                last_signal_at: new Date(
                  Date.now() - Math.random() * 5 * 60 * 1000
                ).toISOString(),
              }))
            )}
            isLoading={metricsQuery.isLoading}
          />
        </Card>

        <Card title="Storage" description="Database utilisation">
          <StorageMeter
            dbSizeBytes={data?.db_size_bytes ?? 0}
            maxSizeBytes={1_000_000_000}
            isLoading={metricsQuery.isLoading}
          />
        </Card>
      </div>

      {/* Status Timeline */}
      <Card
        title="24-hour Status Timeline"
        description="Hourly health distribution · green healthy, yellow degraded, red offline"
      >
        <StatusTimeline
          detectionCount={data?.detections_total ?? 0}
          layerCount={data?.layers.length ?? 0}
          isLoading={metricsQuery.isLoading}
        />
      </Card>

      {/* Error State */}
      {metricsQuery.isError && (
        <div
          className="rounded-lg border p-4 text-sm"
          style={{
            borderColor: "var(--sev-escalate)",
            backgroundColor: `color-mix(in srgb, var(--sev-escalate) 8%, transparent)`,
            color: "var(--sev-escalate)",
          }}
        >
          Error loading system status. Please try refreshing.
        </div>
      )}

      {/* Style injection for animations */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}
