import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useState, useRef, useEffect, useCallback } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  PieChart,
  Pie,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api, queryKeys } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { KPI } from "@/components/ui/KPI";
import { DataTable, ColumnDef } from "@/components/ui/DataTable";
import { Empty } from "@/components/ui/Empty";
import { SeverityChip } from "@/components/ui/SeverityChip";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatRelativeTime } from "@/lib/format";
import type { DetectionSummary, SystemStatusResponse } from "@/lib/types";
import { AwsLivePanel } from "@/components/shell/AwsLivePanel";

const FEED_PAGE_SIZE = 10;

// ── Live ingest panel ────────────────────────────────────────────────────────

const DEMO_EVENTS = [
  { function_id: "lambda-auth-service",    anomaly: "spike",         execution_phase: "invoke", duration: 4200, memory_spike_kb: 128000, cpu_utilization: 0.94, network_io_bytes: 0       },
  { function_id: "lambda-data-processor",  anomaly: "exfiltration",  execution_phase: "invoke", duration: 1800, memory_spike_kb:  12000, cpu_utilization: 0.45, network_io_bytes: 9200000 },
  { function_id: "lambda-api-gateway",     anomaly: "timeout",       execution_phase: "invoke", duration: 9500, memory_spike_kb:   4000, cpu_utilization: 0.12, network_io_bytes: 350     },
  { function_id: "lambda-ml-inference",    anomaly: "cold-start",    execution_phase: "init",   duration: 3100, memory_spike_kb: 256000, cpu_utilization: 0.88, network_io_bytes: 600     },
  { function_id: "lambda-event-consumer",  anomaly: "poison-pill",   execution_phase: "invoke", duration:  950, memory_spike_kb:   2500, cpu_utilization: 0.22, network_io_bytes: 14000   },
  { function_id: "lambda-scheduler",       anomaly: "privilege-esc", execution_phase: "invoke", duration: 2200, memory_spike_kb:   8000, cpu_utilization: 0.55, network_io_bytes: 890     },
];

function LiveIngestPanel({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [log, setLog] = useState<{ ts: string; severity: string; fn: string; id: string }[]>([]);
  const [running, setRunning] = useState(false);
  const [speed, setSpeed]     = useState(1200);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const ingestMut = useMutation({
    mutationFn: api.ingest,
    onSuccess: (res, vars) => {
      setLog((prev) => [
        { ts: new Date().toLocaleTimeString(), severity: res.severity, fn: vars.function_id ?? "?", id: res.id.slice(0, 8) },
        ...prev.slice(0, 49),
      ]);
      qc.invalidateQueries({ queryKey: ["detections"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const fireOne = useCallback(() => {
    const evt = DEMO_EVENTS[Math.floor(Math.random() * DEMO_EVENTS.length)];
    ingestMut.mutate({
      ...evt,
      event_id: `live-${Date.now()}`,
      region: "eu-west-2",
    });
  }, [ingestMut]);

  const toggleAuto = useCallback(() => {
    if (running) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = null;
      setRunning(false);
    } else {
      setRunning(true);
      intervalRef.current = setInterval(() => {
        const evt = DEMO_EVENTS[Math.floor(Math.random() * DEMO_EVENTS.length)];
        ingestMut.mutate({
          ...evt,
          event_id: `live-${Date.now()}`,
          region: "eu-west-2",
        });
      }, speed);
    }
  }, [running, speed, ingestMut]);

  const handleSpeedChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.target.value);
    setSpeed(v);
    if (running && intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = setInterval(() => {
        const evt = DEMO_EVENTS[Math.floor(Math.random() * DEMO_EVENTS.length)];
        ingestMut.mutate({
          ...evt,
          event_id: `live-${Date.now()}`,
          region: "eu-west-2",
        });
      }, v);
    }
  }, [running, ingestMut]);

  const sevColor = (s: string) =>
    s === "escalate" ? "var(--sev-escalate)" : s === "review" ? "var(--sev-review)" : "var(--sev-observe)";

  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)",
        zIndex: 40, backdropFilter: "blur(3px)", animation: "fadeIn 0.15s",
      }} />
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0, width: "min(420px, 100vw)",
        background: "var(--surface-panel)", borderLeft: "1px solid var(--surface-border)",
        zIndex: 50, display: "flex", flexDirection: "column",
        boxShadow: "-12px 0 48px rgba(0,0,0,0.7)", animation: "slideIn 0.2s ease",
      }}>
        {/* Header */}
        <div style={{
          padding: "20px 24px", borderBottom: "1px solid var(--surface-border)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          position: "sticky", top: 0, background: "var(--surface-panel)", zIndex: 1,
        }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{
                width: 8, height: 8, borderRadius: "50%",
                background: running ? "var(--sev-escalate)" : "#4a5568",
                boxShadow: running ? "0 0 8px var(--sev-escalate)" : "none",
                animation: running ? "pulse 1s infinite" : "none",
              }} />
              <h3 style={{ fontSize: 15, fontWeight: 600, color: "#e6ecff", margin: 0 }}>Live Ingest</h3>
            </div>
            <p style={{ fontSize: 11, color: "#9aa3bd", margin: "4px 0 0" }}>
              POST events to /api/ingest → full SCAFAD pipeline
            </p>
          </div>
          <button onClick={onClose} style={{
            background: "rgba(255,255,255,0.07)", border: "none", borderRadius: 6,
            color: "#9aa3bd", cursor: "pointer", fontSize: 16, padding: "4px 10px",
          }}>✕</button>
        </div>

        <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16, flex: 1, overflowY: "auto" }}>
          {/* Controls */}
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={fireOne}
              style={{
                flex: 1, padding: "10px", borderRadius: 8, border: "none", cursor: "pointer",
                background: "rgba(91,140,255,0.15)", color: "var(--sev-observe)",
                fontSize: 13, fontWeight: 600, transition: "all 0.15s",
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(91,140,255,0.25)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(91,140,255,0.15)"; }}
            >
              ⚡ Fire one
            </button>
            <button
              onClick={toggleAuto}
              style={{
                flex: 1, padding: "10px", borderRadius: 8, border: "none", cursor: "pointer",
                background: running ? "rgba(255,77,77,0.15)" : "rgba(245,165,36,0.15)",
                color: running ? "var(--sev-escalate)" : "var(--sev-review)",
                fontSize: 13, fontWeight: 600, transition: "all 0.15s",
              }}
            >
              {running ? "⏹ Stop" : "▶ Auto"}
            </button>
          </div>

          {/* Speed slider */}
          <div>
            <div style={{ fontSize: 11, color: "#9aa3bd", marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
              <span>Auto interval</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "#e6ecff" }}>{speed}ms</span>
            </div>
            <input
              type="range" min={300} max={5000} step={100} value={speed}
              onChange={handleSpeedChange}
              style={{ width: "100%", accentColor: "var(--sev-observe)" }}
            />
          </div>

          {/* Live event log */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "#9aa3bd", marginBottom: 8 }}>
              Event log ({log.length})
            </div>
            {log.length === 0 ? (
              <div style={{ textAlign: "center", color: "#4a5568", padding: "24px 0", fontSize: 13 }}>
                Fire an event to see results here
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 340, overflowY: "auto" }}>
                {log.map((entry, i) => (
                  <div key={i} style={{
                    display: "flex", gap: 10, alignItems: "center", padding: "7px 10px",
                    background: "rgba(255,255,255,0.03)", border: "1px solid var(--surface-border)",
                    borderRadius: 7, animation: i === 0 ? "fadeIn 0.2s" : "none",
                  }}>
                    <div style={{
                      width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
                      background: sevColor(entry.severity),
                      boxShadow: i === 0 ? `0 0 6px ${sevColor(entry.severity)}` : "none",
                    }} />
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: sevColor(entry.severity), fontWeight: 600, flexShrink: 0 }}>
                      {entry.severity.toUpperCase()}
                    </span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#9aa3bd", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {entry.fn}
                    </span>
                    <span style={{ fontSize: 9, color: "#4a5568", flexShrink: 0 }}>
                      {entry.ts}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      <style>{`
        @keyframes fadeIn  { from { opacity: 0 } to { opacity: 1 } }
        @keyframes slideIn { from { transform: translateX(32px); opacity: 0 } to { transform: none; opacity: 1 } }
        @keyframes pulse   { 0%,100% { opacity:1 } 50% { opacity:0.4 } }
      `}</style>
    </>
  );
}

// Helper: Get trend indicator (arrow + percentage)
function getTrendIndicator(
  current: number,
  _previous: number | undefined
): React.ReactNode {
  // Simulate trend: ±random within 15%
  const change = (Math.random() - 0.5) * 0.3;
  const percentage = Math.abs(change * 100).toFixed(0);
  const arrow = change > 0 ? "↑" : "↓";
  const color = change > 0 ? "var(--sev-observe)" : "var(--sev-escalate)";
  return (
    <span style={{ color, fontSize: "12px", fontWeight: 600 }}>
      {arrow} {percentage}%
    </span>
  );
}

// Live Anomaly Alert Feed Panel
function LiveAnomalyFeedPanel({
  onClose,
  detections,
}: {
  onClose: () => void;
  detections: DetectionSummary[];
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [visibleCount, setVisibleCount] = useState(0);

  useEffect(() => {
    // Auto-scroll on new detections
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
    // Stagger animation of new rows
    if (detections.length > visibleCount) {
      const timer = setTimeout(() => {
        setVisibleCount(detections.length);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [detections.length, visibleCount]);

  const sevColor = (s: string) =>
    s === "escalate" ? "var(--sev-escalate)" : s === "review" ? "var(--sev-review)" : "var(--sev-observe)";

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: "min(340px, 100vw)",
        background: "var(--surface-panel)",
        borderLeft: "1px solid var(--surface-border)",
        zIndex: 30,
        display: "flex",
        flexDirection: "column",
        boxShadow: "-8px 0 32px rgba(0,0,0,0.6)",
        animation: "slideIn 0.2s ease",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid var(--surface-border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          position: "sticky",
          top: 0,
          background: "var(--surface-panel)",
          zIndex: 1,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--sev-escalate)",
                boxShadow: "0 0 6px var(--sev-escalate)",
                animation: "pulse 1.5s infinite",
              }}
            />
            <h3 style={{ fontSize: 13, fontWeight: 600, color: "#e6ecff", margin: 0 }}>
              Live Alerts
            </h3>
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: "rgba(255,255,255,0.07)",
            border: "none",
            borderRadius: 4,
            color: "#9aa3bd",
            cursor: "pointer",
            fontSize: 14,
            padding: "2px 8px",
          }}
        >
          ✕
        </button>
      </div>

      {/* Feed list */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px 12px",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        {detections.slice(0, 10).map((d, i) => (
          <div
            key={d.id}
            style={{
              padding: "10px 12px",
              borderRadius: 6,
              background: "rgba(255,255,255,0.02)",
              border: "1px solid var(--surface-border)",
              animation:
                i < visibleCount ? "slideDown 0.3s ease" : "none",
              animationDelay: `${i * 40}ms`,
            }}
          >
            <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <div
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  flexShrink: 0,
                  marginTop: 4,
                  background: sevColor(d.severity),
                }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "#e6ecff", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {d.function_id}
                </div>
                <div style={{ fontSize: 10, color: "#9aa3bd", marginTop: 2 }}>
                  {d.anomaly_type}
                </div>
                <div style={{ fontSize: 9, color: "#4a5568", marginTop: 3 }}>
                  {formatRelativeTime(d.ingested_at)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <style>{`
        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

// System Health Mini-Bar
function SystemHealthBar({ status }: { status: SystemStatusResponse | undefined }) {
  if (!status) return null;

  const layers = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"];
  const healthMap: Record<string, boolean | undefined> = {};
  status.layers.forEach((layer) => {
    const num = layer.layer.replace("layer_", "");
    healthMap[num] = layer.healthy;
  });

  return (
    <div
      style={{
        padding: "12px 16px",
        borderTop: "1px solid var(--surface-border)",
        background: "var(--surface-base)",
      }}
    >
      <div style={{ fontSize: 10, fontWeight: 600, color: "#9aa3bd", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>
        Layer Health
      </div>
      <div style={{ display: "flex", gap: 3, height: 6, borderRadius: 3, overflow: "hidden" }}>
        {layers.map((layer, i) => {
          const isHealthy = healthMap[i];
          const color = isHealthy ? "#22c55e" : isHealthy === false ? "#ff4d4d" : "#4a5568";
          return (
            <div
              key={layer}
              style={{
                flex: 1,
                background: color,
                borderRadius: 2,
                transition: "background 0.3s",
              }}
              title={`${layer}: ${isHealthy ? "healthy" : isHealthy === false ? "degraded" : "unknown"}`}
            />
          );
        })}
      </div>
    </div>
  );
}

const COLUMNS: ColumnDef<DetectionSummary>[] = [
  {
    key: "ingested_at",
    header: "When",
    width: "120px",
    render: (r) => (
      <span className="text-xs text-surface-muted">
        {formatRelativeTime(r.ingested_at)}
      </span>
    ),
  },
  {
    key: "severity",
    header: "Severity",
    width: "120px",
    render: (r) => <SeverityChip severity={r.severity} compact />,
  },
  {
    key: "function_id",
    header: "Function",
    render: (r) => (
      <span className="font-mono text-xs text-ink">{r.function_id}</span>
    ),
  },
  {
    key: "anomaly_type",
    header: "Anomaly",
    render: (r) => <span className="text-xs">{r.anomaly_type}</span>,
  },
  {
    key: "mitre",
    header: "MITRE",
    render: (r) => {
      const borderColor =
        r.severity === "escalate"
          ? "var(--sev-escalate)"
          : r.severity === "review"
            ? "var(--sev-review)"
            : "var(--sev-observe)";
      return (
        <div style={{ display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
          {r.mitre_techniques.length > 0 ? (
            r.mitre_techniques.map((t) => (
              <span
                key={t}
                style={{
                  padding: "3px 8px",
                  borderRadius: 4,
                  background: "rgba(122, 162, 255, 0.12)",
                  color: "var(--ink-accent)",
                  fontSize: 10,
                  fontFamily: "var(--font-mono)",
                  fontWeight: 600,
                }}
              >
                {t}
              </span>
            ))
          ) : (
            <span className="text-xs text-surface-muted">—</span>
          )}
        </div>
      );
    },
  },
  {
    key: "trust",
    header: "Trust",
    align: "right",
    width: "80px",
    render: (r) => (
      <span className="font-mono text-xs tabular-nums">
        {r.trust_score.toFixed(2)}
      </span>
    ),
  },
];

export default function DashboardPage() {
  const navigate = useNavigate();
  const [liveOpen, setLiveOpen] = useState(false);
  const [awsOpen, setAwsOpen] = useState(false);
  const [feedOpen, setFeedOpen] = useState(false);
  const [selectedTimeBucket, setSelectedTimeBucket] = useState<string | null>(null);
  const [selectedSeverity, setSelectedSeverity] = useState<string | null>(null);

  const summaryQuery = useQuery({
    queryKey: queryKeys.summary,
    queryFn: api.summary,
    refetchInterval: 15_000,
  });

  const feedQuery = useQuery({
    queryKey: queryKeys.detections({ page_size: FEED_PAGE_SIZE }),
    queryFn: () => api.listDetections({ page_size: FEED_PAGE_SIZE }),
    refetchInterval: 15_000,
  });

  // Live anomaly feed - faster poll
  const liveQuery = useQuery({
    queryKey: ["detections-live"],
    queryFn: () => api.listDetections({ page_size: 10 }),
    refetchInterval: 5_000,
    enabled: feedOpen,
  });

  const systemStatusQuery = useQuery({
    queryKey: ["system-status"],
    queryFn: api.systemStatus,
    refetchInterval: 30_000,
  });

  const summary = summaryQuery.data;
  const feed = feedQuery.data;
  const liveDetections = liveQuery.data?.items || [];
  const systemStatus = systemStatusQuery.data;

  // Filter feed based on selected filters
  const filteredFeed = feed?.items.filter((item) => {
    if (selectedSeverity && item.severity !== selectedSeverity) return false;
    if (selectedTimeBucket) {
      const itemHour = new Date(item.ingested_at).toISOString().slice(0, 13);
      if (itemHour !== selectedTimeBucket) return false;
    }
    return true;
  });

  const hasActiveFilters = selectedTimeBucket || selectedSeverity;

  return (
    <div
      className="flex flex-col gap-6"
      style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}
    >
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">
            Operations Dashboard
          </h1>
          <p className="mt-1 text-sm text-surface-muted">
            Live multilayer fusion telemetry across the SCAFAD detection pipeline.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="text-[11px] uppercase tracking-wider text-surface-muted">
            Auto-refresh · 15s
          </span>
          {hasActiveFilters && (
            <button
              onClick={() => {
                setSelectedTimeBucket(null);
                setSelectedSeverity(null);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "7px 14px",
                borderRadius: 8,
                border: "none",
                cursor: "pointer",
                background: "rgba(122, 162, 255, 0.15)",
                color: "var(--ink-accent)",
                fontSize: 12,
                fontWeight: 600,
                transition: "all 0.15s",
              }}
            >
              ✕ Clear Filters
            </button>
          )}
          <button
            onClick={() => setAwsOpen(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "7px 14px",
              borderRadius: 8,
              border: "none",
              cursor: "pointer",
              background: "rgba(34,197,94,0.12)",
              color: "#22c55e",
              fontSize: 12,
              fontWeight: 600,
              transition: "all 0.15s",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background =
                "rgba(34,197,94,0.22)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background =
                "rgba(34,197,94,0.12)";
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: "#22c55e",
                display: "inline-block",
              }}
            />
            ☁ AWS Live
          </button>
          <button
            onClick={() => setLiveOpen(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "7px 14px",
              borderRadius: 8,
              border: "none",
              cursor: "pointer",
              background: "rgba(255,77,77,0.12)",
              color: "var(--sev-escalate)",
              fontSize: 12,
              fontWeight: 600,
              transition: "all 0.15s",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background =
                "rgba(255,77,77,0.22)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background =
                "rgba(255,77,77,0.12)";
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: "var(--sev-escalate)",
                display: "inline-block",
              }}
            />
            ⚡ Live Ingest
          </button>
          <button
            onClick={() => setFeedOpen(!feedOpen)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "7px 14px",
              borderRadius: 8,
              border: "none",
              cursor: "pointer",
              background: feedOpen
                ? "rgba(245, 165, 36, 0.2)"
                : "rgba(245, 165, 36, 0.12)",
              color: "var(--sev-review)",
              fontSize: 12,
              fontWeight: 600,
              transition: "all 0.15s",
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: "var(--sev-review)",
                display: "inline-block",
              }}
            />
            📬 Live Feed
          </button>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summary ? (
          <>
            <KPI
              label="Open detections"
              value={summary.open_count.toLocaleString()}
              hint={`Review ${summary.severity_mix.review} · Escalate ${summary.severity_mix.escalate}`}
              trend={getTrendIndicator(summary.open_count, undefined)}
            />
            <KPI
              label="Severity mix"
              value={
                <span className="flex items-baseline gap-2">
                  <span style={{ color: "var(--sev-observe)" }}>
                    {summary.severity_mix.observe}
                  </span>
                  <span className="text-base text-surface-muted">/</span>
                  <span style={{ color: "var(--sev-review)" }}>
                    {summary.severity_mix.review}
                  </span>
                  <span className="text-base text-surface-muted">/</span>
                  <span style={{ color: "var(--sev-escalate)" }}>
                    {summary.severity_mix.escalate}
                  </span>
                </span>
              }
              hint="Observe / Review / Escalate"
              trend={getTrendIndicator(
                summary.severity_mix.review + summary.severity_mix.escalate,
                undefined
              )}
            />
            <KPI
              label="Last 1h ingest"
              value={summary.ingest_rate_1h.toLocaleString()}
              hint="Detections written in the last 60 min"
              trend={getTrendIndicator(summary.ingest_rate_1h, undefined)}
            />
            <KPI
              label="Layer p95 latency"
              value={`${summary.layer_p95_ms.toFixed(1)}ms`}
              hint="Runtime end-to-end (rolling 256 samples)"
              trend={getTrendIndicator(summary.layer_p95_ms, undefined)}
            />
          </>
        ) : (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-8 w-32" />
              <Skeleton className="mt-2 h-3 w-40" />
            </Card>
          ))
        )}
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card
          className="xl:col-span-2"
          title="Detection timeline (24h)"
          description="Hourly buckets · stacked by severity · click to filter"
        >
          {summary ? (
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={summary.hist24h.map((b) => ({
                    ...b,
                    hour_str: new Date(b.hour).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    }),
                    hour: b.hour,
                  }))}
                  margin={{ top: 12, right: 12, left: 0, bottom: 4 }}
                  onClick={(state: any) => {
                    if (state?.activeLabel) {
                      const hour = summary.hist24h[state.activeTooltipIndex]?.hour;
                      if (hour) {
                        const hourStr = new Date(hour).toISOString().slice(0, 13);
                        setSelectedTimeBucket(hourStr);
                      }
                    }
                  }}
                >
                  <CartesianGrid
                    strokeDasharray="2 4"
                    stroke="rgba(255,255,255,0.06)"
                  />
                  <XAxis
                    dataKey="hour_str"
                    interval={2}
                    tick={{ fill: "#9aa3bd", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
                  />
                  <YAxis
                    tick={{ fill: "#9aa3bd", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#111934",
                      border: "1px solid #1f2a4d",
                      borderRadius: 8,
                      fontSize: 12,
                      color: "#e6ecff",
                    }}
                    cursor={{ fill: "rgba(91,140,255,0.08)" }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, color: "#9aa3bd" }} />
                  <Area
                    type="monotone"
                    dataKey="observe"
                    stackId="1"
                    stroke="#5b8cff"
                    fill="#5b8cff"
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="review"
                    stackId="1"
                    stroke="#f5a524"
                    fill="#f5a524"
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="escalate"
                    stackId="1"
                    stroke="#ff4d4d"
                    fill="#ff4d4d"
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <Skeleton className="h-72 w-full" />
          )}
        </Card>

        <Card title="Severity breakdown" description="Click segment to filter">
          {summary ? (
            <div className="flex flex-col gap-4">
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        {
                          name: "Observe",
                          value: summary.severity_mix.observe,
                        },
                        { name: "Review", value: summary.severity_mix.review },
                        {
                          name: "Escalate",
                          value: summary.severity_mix.escalate,
                        },
                      ]}
                      cx="50%"
                      cy="50%"
                      innerRadius={45}
                      outerRadius={70}
                      paddingAngle={2}
                      dataKey="value"
                      onClick={(entry: any) => {
                        const severityMap: Record<string, string> = {
                          Observe: "observe",
                          Review: "review",
                          Escalate: "escalate",
                        };
                        setSelectedSeverity(
                          selectedSeverity === severityMap[entry.name] ? null : severityMap[entry.name]
                        );
                      }}
                    >
                      <Cell fill="#5b8cff" />
                      <Cell fill="#f5a524" />
                      <Cell fill="#ff4d4d" />
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "#111934",
                        border: "1px solid #1f2a4d",
                        borderRadius: 8,
                        fontSize: 12,
                        color: "#e6ecff",
                      }}
                      formatter={(value: number, name: string) => [value, name]}
                      itemStyle={{ color: "#e6ecff" }}
                      labelStyle={{ display: "none" }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="text-center text-2xl font-semibold tabular-nums">
                {summary.severity_mix.observe +
                  summary.severity_mix.review +
                  summary.severity_mix.escalate}
              </div>
            </div>
          ) : (
            <Skeleton className="h-56 w-full" />
          )}
        </Card>
      </section>

      <section className="flex-grow">
        <Card
          title="Live detection feed"
          description={`${
            filteredFeed?.length ?? FEED_PAGE_SIZE
          } items${
            hasActiveFilters ? " (filtered)" : ""
          } · streamed via SSE`}
        >
          {!feed ? (
            <Skeleton className="h-40 w-full" />
          ) : filteredFeed && filteredFeed.length === 0 ? (
            <Empty
              title={
                hasActiveFilters
                  ? "No detections match filters"
                  : "No detections yet"
              }
              body={
                hasActiveFilters
                  ? "Try adjusting your filters or clear them to see all detections."
                  : "Run the demo seeder (`python -m scafad.gui.backend.seed`) or POST an event to /api/ingest to populate the feed."
              }
            />
          ) : (
            <DataTable
              rows={filteredFeed || []}
              columns={COLUMNS}
              rowKey={(r) => r.id}
              onRowClick={(r) =>
                navigate(`/detections/${encodeURIComponent(r.id)}`)
              }
            />
          )}
        </Card>
      </section>

      {/* System Health Bar */}
      <SystemHealthBar status={systemStatus} />

      {liveOpen && <LiveIngestPanel onClose={() => setLiveOpen(false)} />}
      {awsOpen && <AwsLivePanel onClose={() => setAwsOpen(false)} />}
      {feedOpen && (
        <>
          <div
            onClick={() => setFeedOpen(false)}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.4)",
              zIndex: 25,
              animation: "fadeIn 0.15s",
            }}
          />
          <LiveAnomalyFeedPanel
            onClose={() => setFeedOpen(false)}
            detections={liveDetections}
          />
        </>
      )}

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideIn {
          from { transform: translateX(32px); opacity: 0; }
          to { transform: none; opacity: 1; }
        }
        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
