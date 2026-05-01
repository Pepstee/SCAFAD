/**
 * Functions page — per-Lambda-function risk explorer.
 *
 * Features:
 *   • Left panel: search, severity tabs with counts, sort control, table-style rows
 *   • Right drawer: 30-day sparkline, KPI tiles, MITRE breakdown, recent detections, linked cases
 */
import { useState, useMemo, useCallback, memo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  BarChart,
  Bar,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  Cell,
} from "recharts";
import { api } from "../lib/api";
import { SeverityChip } from "../components/ui/SeverityChip";
import { Skeleton } from "../components/ui/Skeleton";
import { formatRelativeTime } from "../lib/format";
import type {
  FunctionListResponse,
  FunctionRollup,
  FunctionDetail,
  CaseStatus,
} from "../lib/types";

// ── types ─────────────────────────────────────────────────────────────────────

type SevFilter = "all" | "escalate" | "review" | "observe";
type SortKey = "last_seen" | "count_24h" | "count_7d" | "risk_score";

// ── constants ─────────────────────────────────────────────────────────────────

const SEV_TABS: { label: string; value: SevFilter; color: string }[] = [
  { label: "All",      value: "all",      color: "#9aa3bd"             },
  { label: "Escalate", value: "escalate", color: "var(--sev-escalate)" },
  { label: "Review",   value: "review",   color: "var(--sev-review)"   },
  { label: "Observe",  value: "observe",  color: "var(--sev-observe)"  },
];

const SORT_OPTIONS: { label: string; value: SortKey }[] = [
  { label: "Last Seen",     value: "last_seen"   },
  { label: "Most Hits 24h", value: "count_24h"   },
  { label: "Most Hits 7d",  value: "count_7d"    },
  { label: "Risk Score",    value: "risk_score"  },
];

// ── helpers ───────────────────────────────────────────────────────────────────

function sevColor(sev: string): string {
  if (sev === "escalate") return "var(--sev-escalate)";
  if (sev === "review")   return "var(--sev-review)";
  return "var(--sev-observe)";
}

function sevBorderColor(sev: string): string {
  if (sev === "escalate") return "rgba(255,77,77,0.7)";
  if (sev === "review")   return "rgba(245,165,36,0.7)";
  return "rgba(91,140,255,0.7)";
}

function caseStatusColor(status: CaseStatus): string {
  if (status === "open")      return "var(--sev-escalate)";
  if (status === "triage")    return "var(--sev-review)";
  if (status === "contained") return "var(--sev-observe)";
  return "#4a5568";
}

function computeRiskScore(func: FunctionRollup): number {
  const sevScore = func.severity_max === "escalate" ? 60 : func.severity_max === "review" ? 35 : 10;
  const hitScore = Math.min((func.count_7d / 100) * 30, 30);
  const caseScore = Math.min(func.open_case_count * 5, 10);
  return Math.round(sevScore + hitScore + caseScore);
}

function riskScoreColor(score: number): string {
  if (score >= 67) return "var(--sev-escalate)";
  if (score >= 34) return "var(--sev-review)";
  return "var(--sev-observe)";
}

function riskScoreBg(score: number): string {
  if (score >= 67) return "rgba(255,77,77,0.15)";
  if (score >= 34) return "rgba(245,165,36,0.15)";
  return "rgba(91,140,255,0.15)";
}

// ── 30-day sparkline chart ────────────────────────────────────────────────────

function SparklineChart30({
  data,
}: {
  data: { date?: string; bucket_start?: string; count: number; severity_max?: string }[];
}) {
  if (!data || data.length === 0) {
    return (
      <div style={{
        height: 80, background: "rgba(255,255,255,0.03)",
        borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <span style={{ fontSize: 11, color: "#4a5568" }}>No activity data</span>
      </div>
    );
  }

  const chartData = data.map((b, i) => ({
    i,
    count: b.count,
    sev: b.severity_max ?? "observe",
    label: b.date ?? b.bucket_start ?? String(i),
  }));

  return (
    <ResponsiveContainer width="100%" height={80}>
      <BarChart data={chartData} margin={{ top: 4, right: 2, left: 2, bottom: 0 }} barCategoryGap={2}>
        <XAxis dataKey="i" hide />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
          contentStyle={{
            background: "#111934", border: "1px solid #1f2a4d",
            borderRadius: 6, fontSize: 11, color: "#e6ecff", padding: "4px 10px",
          }}
          formatter={(v: number, _: string, props: { payload?: { sev?: string } }) => [
            `${v} hit${v !== 1 ? "s" : ""}`,
            props.payload?.sev ?? "observe",
          ]}
          labelFormatter={(_: unknown, payload: { payload?: { label?: string } }[]) =>
            payload?.[0]?.payload?.label ?? ""
          }
        />
        <Bar dataKey="count" radius={[2, 2, 0, 0]} maxBarSize={16} isAnimationActive={false}>
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={sevColor(entry.sev)} opacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── risk score badge ──────────────────────────────────────────────────────────

function RiskBadge({ score }: { score: number }) {
  return (
    <span style={{
      fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700,
      color: riskScoreColor(score), background: riskScoreBg(score),
      border: `1px solid ${riskScoreColor(score)}44`,
      borderRadius: 6, padding: "2px 7px", flexShrink: 0,
      minWidth: 36, textAlign: "center",
    }}>
      {score}
    </span>
  );
}

// ── count chip ────────────────────────────────────────────────────────────────

function CountChip({ label, value }: { label: string; value: number }) {
  return (
    <span style={{
      fontSize: 10, fontFamily: "var(--font-mono)",
      color: value > 0 ? "#c8d0e7" : "#4a5568",
      background: value > 0 ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.03)",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: 5, padding: "1px 6px", flexShrink: 0,
    }}>
      {value} <span style={{ opacity: 0.6 }}>{label}</span>
    </span>
  );
}

// ── MITRE chips ───────────────────────────────────────────────────────────────

function MitreTechChips({ techniques }: { techniques: string[] }) {
  const show = techniques.slice(0, 2);
  const rest = techniques.length - 2;
  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "nowrap", overflow: "hidden", flexShrink: 0 }}>
      {show.map((t) => (
        <span key={t} style={{
          fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--sev-observe)",
          background: "rgba(91,140,255,0.1)", border: "1px solid rgba(91,140,255,0.2)",
          borderRadius: 4, padding: "1px 5px", whiteSpace: "nowrap",
        }}>
          {t}
        </span>
      ))}
      {rest > 0 && (
        <span style={{ fontSize: 9, color: "#4a5568", whiteSpace: "nowrap" }}>
          +{rest} more
        </span>
      )}
    </div>
  );
}

// ── function row ──────────────────────────────────────────────────────────────

const FunctionRow = memo(function FunctionRow({
  func,
  isSelected,
  onClick,
}: {
  func: FunctionRollup;
  isSelected: boolean;
  onClick: () => void;
}) {
  const sev = func.severity_max || "observe";
  const riskScore = computeRiskScore(func);
  const [hovered, setHovered] = useState(false);

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "10px 14px",
        background: isSelected
          ? "rgba(91,140,255,0.12)"
          : hovered
          ? "rgba(255,255,255,0.05)"
          : "transparent",
        border: "none",
        borderBottom: "1px solid rgba(255,255,255,0.05)",
        borderLeft: isSelected ? "3px solid var(--sev-observe)" : "3px solid transparent",
        cursor: "pointer", textAlign: "left", width: "100%",
        transition: "background 0.12s ease, border-left-color 0.12s ease",
        minHeight: 52,
      }}
    >
      {/* Severity left bar */}
      <div style={{
        width: 4, height: 36, borderRadius: 2, flexShrink: 0,
        background: sevBorderColor(sev),
      }} />

      {/* Function name + MITRE chips */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600,
          color: "#e6ecff", overflow: "hidden", textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}>
          {func.function_id}
        </div>
        {func.top_mitre && func.top_mitre.length > 0 && (
          <div style={{ display: "flex", gap: 6, marginTop: 4, alignItems: "center" }}>
            <MitreTechChips techniques={func.top_mitre} />
          </div>
        )}
      </div>

      {/* Right-side metadata */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        {/* 24h / 7d chips */}
        <div style={{ display: "flex", gap: 4 }}>
          <CountChip label="24h" value={func.count_24h} />
          <CountChip label="7d"  value={func.count_7d}  />
        </div>

        {/* Open cases badge */}
        {func.open_case_count > 0 && (
          <span style={{
            fontSize: 10, fontWeight: 700, fontFamily: "var(--font-mono)",
            color: "var(--sev-escalate)",
            background: "rgba(255,77,77,0.15)", border: "1px solid rgba(255,77,77,0.3)",
            borderRadius: 5, padding: "1px 6px",
          }}>
            {func.open_case_count} case{func.open_case_count !== 1 ? "s" : ""}
          </span>
        )}

        {/* Last seen */}
        <span style={{ fontSize: 10, color: "#4a5568", whiteSpace: "nowrap", minWidth: 48, textAlign: "right" }}>
          {formatRelativeTime(func.last_seen)}
        </span>

        {/* Risk score badge */}
        <RiskBadge score={riskScore} />
      </div>
    </button>
  );
});

// ── detail panel ──────────────────────────────────────────────────────────────

function FunctionDetailPanel({
  func,
  onClose,
}: {
  func: FunctionRollup;
  onClose: () => void;
}) {
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ["function-detail", func.function_id, 30],
    queryFn: () => api.getFunctionDetail(func.function_id, 30),
  });
  const detail = data as FunctionDetail | undefined;

  const sev = func.severity_max || "observe";
  const riskScore = computeRiskScore(func);

  const topMitre = useMemo(() => {
    if (!detail?.top_mitre) return [];
    return detail.top_mitre;
  }, [detail]);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
          zIndex: 40, backdropFilter: "blur(2px)",
          animation: "fadeIn 0.15s ease",
        }}
      />

      {/* Drawer */}
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0,
        width: "min(540px, 100vw)",
        background: "var(--surface-panel)",
        borderLeft: "1px solid var(--surface-border)",
        zIndex: 50, display: "flex", flexDirection: "column",
        boxShadow: "-16px 0 48px rgba(0,0,0,0.7)",
        animation: "slideInRight 0.2s ease",
        overflowY: "auto",
      }}>

        {/* ── Header ── */}
        <div style={{
          padding: "18px 20px",
          borderBottom: "1px solid var(--surface-border)",
          position: "sticky", top: 0,
          background: "var(--surface-panel)", zIndex: 2,
          display: "flex", alignItems: "flex-start", gap: 12,
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <div style={{
                width: 4, height: 20, borderRadius: 2, flexShrink: 0,
                background: sevBorderColor(sev),
              }} />
              <SeverityChip severity={sev as "observe" | "review" | "escalate"} compact />
              {func.open_case_count > 0 && (
                <span style={{
                  fontSize: 10, fontWeight: 700,
                  color: "var(--sev-escalate)",
                  background: "rgba(255,77,77,0.15)", border: "1px solid rgba(255,77,77,0.3)",
                  borderRadius: 5, padding: "2px 7px",
                }}>
                  {func.open_case_count} open case{func.open_case_count !== 1 ? "s" : ""}
                </span>
              )}
              <RiskBadge score={riskScore} />
            </div>
            <div style={{
              fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600,
              color: "#e6ecff", marginTop: 6,
              wordBreak: "break-all", lineHeight: 1.4,
            }}>
              {func.function_id}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <button
              onClick={() => navigate(`/inbox?function_id=${encodeURIComponent(func.function_id)}`)}
              style={{
                padding: "6px 12px", borderRadius: 7,
                background: "rgba(91,140,255,0.15)",
                border: "1px solid rgba(91,140,255,0.35)",
                color: "var(--sev-observe)", fontSize: 11, fontWeight: 600,
                cursor: "pointer", whiteSpace: "nowrap",
              }}
            >
              View in Inbox
            </button>
            <button
              onClick={onClose}
              style={{
                background: "rgba(255,255,255,0.07)", border: "none", borderRadius: 6,
                color: "#9aa3bd", cursor: "pointer", fontSize: 15,
                padding: "5px 10px", lineHeight: 1,
              }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* ── Body ── */}
        {isLoading ? (
          <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : (
          <div style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 20 }}>

            {/* ── 30-day sparkline ── */}
            <section>
              <div style={{
                fontSize: 10, fontWeight: 600, textTransform: "uppercase",
                letterSpacing: "0.08em", color: "#9aa3bd", marginBottom: 8,
              }}>
                30-day activity
              </div>
              <div style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid var(--surface-border)",
                borderRadius: 8, padding: "10px 10px 6px",
              }}>
                <SparklineChart30 data={detail?.sparkline ?? []} />
              </div>
            </section>

            {/* ── KPI tiles ── */}
            <section>
              <div style={{
                fontSize: 10, fontWeight: 600, textTransform: "uppercase",
                letterSpacing: "0.08em", color: "#9aa3bd", marginBottom: 8,
              }}>
                Risk breakdown
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
                {/* Total detections 7d */}
                <div style={{
                  padding: "12px 10px", borderRadius: 8, textAlign: "center",
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid var(--surface-border)",
                }}>
                  <div style={{
                    fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700,
                    color: "#e6ecff",
                  }}>
                    {func.count_7d}
                  </div>
                  <div style={{ fontSize: 9, color: "#9aa3bd", marginTop: 3, lineHeight: 1.3 }}>
                    Total Detections (7d)
                  </div>
                </div>

                {/* Open cases */}
                <div style={{
                  padding: "12px 10px", borderRadius: 8, textAlign: "center",
                  background: func.open_case_count > 0
                    ? "rgba(255,77,77,0.08)" : "rgba(255,255,255,0.04)",
                  border: func.open_case_count > 0
                    ? "1px solid rgba(255,77,77,0.25)" : "1px solid var(--surface-border)",
                }}>
                  <div style={{
                    fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700,
                    color: func.open_case_count > 0 ? "var(--sev-escalate)" : "#e6ecff",
                  }}>
                    {func.open_case_count}
                  </div>
                  <div style={{ fontSize: 9, color: "#9aa3bd", marginTop: 3, lineHeight: 1.3 }}>
                    Open Cases
                  </div>
                </div>

                {/* Top MITRE technique */}
                <div style={{
                  padding: "12px 10px", borderRadius: 8, textAlign: "center",
                  background: "rgba(91,140,255,0.06)",
                  border: "1px solid rgba(91,140,255,0.15)",
                }}>
                  <div style={{
                    fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 700,
                    color: "var(--sev-observe)", overflow: "hidden",
                    textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {func.top_mitre?.[0] ?? "—"}
                  </div>
                  <div style={{ fontSize: 9, color: "#9aa3bd", marginTop: 3, lineHeight: 1.3 }}>
                    Top MITRE Technique
                  </div>
                </div>
              </div>
            </section>

            {/* ── MITRE techniques ── */}
            {topMitre.length > 0 && (
              <section>
                <div style={{
                  fontSize: 10, fontWeight: 600, textTransform: "uppercase",
                  letterSpacing: "0.08em", color: "#9aa3bd", marginBottom: 8,
                }}>
                  MITRE techniques
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {topMitre.map((chip) => (
                    <div key={chip.id} style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center",
                      padding: "7px 10px",
                      background: "rgba(91,140,255,0.06)",
                      border: "1px solid rgba(91,140,255,0.15)",
                      borderRadius: 6,
                    }}>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--sev-observe)" }}>
                        {chip.id}
                      </span>
                      <span style={{
                        fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700,
                        color: "#e6ecff", background: "rgba(255,255,255,0.08)",
                        borderRadius: 4, padding: "1px 6px",
                      }}>
                        {chip.count}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* ── Recent detections (last 5) ── */}
            {detail?.recent_detections && detail.recent_detections.length > 0 && (
              <section>
                <div style={{
                  fontSize: 10, fontWeight: 600, textTransform: "uppercase",
                  letterSpacing: "0.08em", color: "#9aa3bd", marginBottom: 8,
                }}>
                  Recent detections
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                  {detail.recent_detections.slice(0, 5).map((det) => (
                    <button
                      key={det.id}
                      onClick={() => navigate(`/detections/${encodeURIComponent(det.id)}`)}
                      style={{
                        display: "flex", gap: 10, alignItems: "center",
                        padding: "8px 10px",
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid var(--surface-border)",
                        borderRadius: 7, cursor: "pointer", textAlign: "left",
                        width: "100%", transition: "background 0.1s",
                      }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.08)";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.04)";
                      }}
                    >
                      <SeverityChip severity={det.severity} compact />
                      <span style={{
                        fontSize: 11, color: "#9aa3bd", flex: 1,
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      }}>
                        {det.anomaly_type}
                      </span>
                      <span style={{ fontSize: 10, color: "#4a5568", whiteSpace: "nowrap" }}>
                        {formatRelativeTime(det.ingested_at)}
                      </span>
                    </button>
                  ))}
                </div>
              </section>
            )}

            {/* ── Linked cases ── */}
            {detail?.linked_cases && detail.linked_cases.length > 0 && (
              <section>
                <div style={{
                  fontSize: 10, fontWeight: 600, textTransform: "uppercase",
                  letterSpacing: "0.08em", color: "#9aa3bd", marginBottom: 8,
                }}>
                  Linked cases
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {detail.linked_cases.map((c) => (
                    <div
                      key={c.case_id}
                      style={{
                        padding: "10px 12px",
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid var(--surface-border)",
                        borderRadius: 8,
                        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10,
                      }}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: 12, color: "#e6ecff", fontWeight: 500,
                          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        }}>
                          {c.title}
                        </div>
                        <div style={{
                          fontSize: 10, color: "#4a5568", marginTop: 2,
                          fontFamily: "var(--font-mono)",
                        }}>
                          {c.case_id.slice(0, 8)}…
                        </div>
                      </div>
                      <span style={{
                        fontSize: 10, fontWeight: 600, textTransform: "uppercase",
                        letterSpacing: "0.06em",
                        color: caseStatusColor(c.status),
                        padding: "2px 8px",
                        background: `${caseStatusColor(c.status)}22`,
                        borderRadius: 99, flexShrink: 0,
                      }}>
                        {c.status}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

          </div>
        )}
      </div>
    </>
  );
}

// ── severity tab counts ───────────────────────────────────────────────────────

function tabCounts(items: FunctionRollup[]): Record<SevFilter, number> {
  const counts: Record<SevFilter, number> = { all: items.length, escalate: 0, review: 0, observe: 0 };
  for (const f of items) {
    if (f.severity_max === "escalate")      counts.escalate++;
    else if (f.severity_max === "review")   counts.review++;
    else                                    counts.observe++;
  }
  return counts;
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function FunctionsPage() {
  const [sevFilter, setSevFilter] = useState<SevFilter>("all");
  const [search,    setSearch]    = useState("");
  const [sortKey,   setSortKey]   = useState<SortKey>("last_seen");
  const [selected,  setSelected]  = useState<FunctionRollup | null>(null);
  const PAGE_SIZE = 50;

  const { data: data_, isLoading } = useQuery({
    queryKey: ["functions", { sevFilter, PAGE_SIZE }],
    queryFn: () =>
      api.getFunctions({
        severity:  sevFilter === "all" ? undefined : sevFilter,
        sort:      sortKey === "risk_score" ? undefined : sortKey,
        page:      1,
        page_size: PAGE_SIZE,
      }),
    refetchInterval: 30_000,
  });
  const data = data_ as FunctionListResponse | undefined;

  // client-side search + sort
  const filtered = useMemo(() => {
    if (!data?.items) return [];
    let items = data.items as FunctionRollup[];

    if (search.trim()) {
      const q = search.toLowerCase();
      items = items.filter((f) => f.function_id.toLowerCase().includes(q));
    }

    const sorted = [...items];
    if (sortKey === "count_24h") {
      sorted.sort((a, b) => b.count_24h - a.count_24h);
    } else if (sortKey === "count_7d") {
      sorted.sort((a, b) => b.count_7d - a.count_7d);
    } else if (sortKey === "risk_score") {
      sorted.sort((a, b) => computeRiskScore(b) - computeRiskScore(a));
    } else {
      sorted.sort((a, b) => new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime());
    }

    return sorted;
  }, [data, search, sortKey]);

  const counts = useMemo(() => tabCounts(data?.items ?? []), [data]);

  const handleSelectFunc = useCallback((func: FunctionRollup) => {
    setSelected((prev) => (prev?.function_id === func.function_id ? null : func));
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0, height: "100%" }}>

      {/* ── Page header ── */}
      <header style={{
        display: "flex", alignItems: "flex-end", justifyContent: "space-between",
        flexWrap: "wrap", gap: 12, marginBottom: 16,
      }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: "#e6ecff", margin: 0 }}>
            Functions
          </h1>
          <p style={{ marginTop: 4, fontSize: 12, color: "#9aa3bd", margin: "4px 0 0" }}>
            {isLoading
              ? "Loading…"
              : `${data?.total ?? 0} Lambda function${data?.total !== 1 ? "s" : ""} monitored`}
          </p>
        </div>
      </header>

      {/* ── Controls row ── */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        flexWrap: "wrap", marginBottom: 12,
      }}>
        {/* Search */}
        <input
          type="text"
          placeholder="Search function ID…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: "7px 13px", borderRadius: 8,
            border: "1px solid var(--surface-border)",
            background: "var(--surface-panel)", color: "#e6ecff",
            fontSize: 12, outline: "none", width: 220, flexShrink: 0,
          }}
          onFocus={(e) => { (e.currentTarget).style.borderColor = "rgba(91,140,255,0.5)"; }}
          onBlur={(e)  => { (e.currentTarget).style.borderColor = "var(--surface-border)"; }}
        />

        {/* Sort */}
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
          style={{
            padding: "7px 12px", borderRadius: 8,
            border: "1px solid var(--surface-border)",
            background: "var(--surface-panel)", color: "#9aa3bd",
            fontSize: 12, outline: "none", cursor: "pointer",
          }}
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* ── Severity filter tabs ── */}
      <div style={{
        display: "flex", gap: 2,
        borderBottom: "1px solid var(--surface-border)",
      }}>
        {SEV_TABS.map((tab) => {
          const active = sevFilter === tab.value;
          return (
            <button
              key={tab.value}
              onClick={() => setSevFilter(tab.value)}
              style={{
                padding: "8px 16px", border: "none", cursor: "pointer",
                fontSize: 12, fontWeight: active ? 600 : 400,
                background: active ? "rgba(255,255,255,0.06)" : "transparent",
                color: active ? tab.color : "#4a5568",
                borderBottom: active ? `2px solid ${tab.color}` : "2px solid transparent",
                transition: "all 0.15s", display: "flex", alignItems: "center", gap: 6,
              }}
            >
              {tab.label}
              <span style={{
                fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 700,
                color: active ? tab.color : "#4a5568",
                background: active ? `${tab.color}22` : "rgba(255,255,255,0.05)",
                borderRadius: 99, padding: "1px 6px",
              }}>
                {counts[tab.value]}
              </span>
            </button>
          );
        })}
      </div>

      {/* ── Function list ── */}
      <div style={{
        background: "var(--surface-panel)",
        border: "1px solid var(--surface-border)",
        borderTop: "none",
        borderRadius: "0 0 10px 10px",
        overflow: "hidden",
        flex: 1,
      }}>
        {/* Column headers */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "7px 14px 7px 28px",
          background: "rgba(255,255,255,0.03)",
          borderBottom: "1px solid var(--surface-border)",
        }}>
          <span style={{
            flex: 1, fontSize: 10, color: "#4a5568", fontWeight: 600,
            textTransform: "uppercase", letterSpacing: "0.06em",
          }}>
            Function
          </span>
          <span style={{
            fontSize: 10, color: "#4a5568", fontWeight: 600,
            textTransform: "uppercase", letterSpacing: "0.06em",
            minWidth: 120, textAlign: "right",
          }}>
            24h / 7d
          </span>
          <span style={{
            fontSize: 10, color: "#4a5568", fontWeight: 600,
            textTransform: "uppercase", letterSpacing: "0.06em",
            minWidth: 60, textAlign: "right",
          }}>
            Last seen
          </span>
          <span style={{
            fontSize: 10, color: "#4a5568", fontWeight: 600,
            textTransform: "uppercase", letterSpacing: "0.06em",
            minWidth: 36, textAlign: "center",
          }}>
            Risk
          </span>
        </div>

        {/* Rows */}
        {isLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                <Skeleton className="h-10 w-full" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "60px 20px",
            color: "#4a5568", fontSize: 13,
          }}>
            {search
              ? `No functions matching "${search}"`
              : "No functions in this severity band yet"}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {filtered.map((func) => (
              <FunctionRow
                key={func.function_id}
                func={func}
                isSelected={selected?.function_id === func.function_id}
                onClick={() => handleSelectFunc(func)}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Detail drawer ── */}
      {selected && (
        <FunctionDetailPanel
          func={selected}
          onClose={() => setSelected(null)}
        />
      )}

      <style>{`
        @keyframes fadeIn       { from { opacity: 0 }                             to { opacity: 1 } }
        @keyframes slideInRight { from { transform: translateX(40px); opacity: 0 } to { transform: none; opacity: 1 } }
      `}</style>
    </div>
  );
}
