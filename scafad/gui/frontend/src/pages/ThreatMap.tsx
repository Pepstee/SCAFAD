/**
 * ThreatMap --- MITRE ATT&CK Navigator-style heatmap for SCAFAD.
 *
 * True matrix layout: tactics as columns, techniques as rows.
 * Clicking any active cell opens a right-side drawer with paginated detections.
 */
import { useState, useCallback, useMemo, useRef, memo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { SeverityChip } from "../components/ui/SeverityChip";
import { Skeleton } from "../components/ui/Skeleton";
import { formatRelativeTime } from "../lib/format";
import type {
  ThreatMapResponse,
  ThreatMapGridResponse,
  ThreatMapCell,
  TechniqueDef,
  DetectionSummary,
} from "../lib/types";

// -- constants ----------------------------------------------------------------

const WINDOW_OPTIONS = [
  { label: "24 h", value: "24h" },
  { label: "7 d",  value: "7d"  },
  { label: "30 d", value: "30d" },
];

/** Canonical left-to-right column order */
const TACTIC_ORDER = [
  "execution",
  "persistence",
  "privilege-escalation",
  "defense-evasion",
  "credential-access",
  "discovery",
  "lateral-movement",
  "collection",
  "exfiltration",
  "impact",
] as const;

const TACTIC_LABELS: Record<string, string> = {
  "execution":            "Execution",
  "persistence":          "Persistence",
  "privilege-escalation": "Priv. Escalation",
  "defense-evasion":      "Defense Evasion",
  "credential-access":    "Cred. Access",
  "discovery":            "Discovery",
  "lateral-movement":     "Lateral Movement",
  "collection":           "Collection",
  "exfiltration":         "Exfiltration",
  "impact":               "Impact",
};

const TACTIC_ICONS: Record<string, string> = {
  "execution":            "⚡",
  "persistence":          "🔒",
  "privilege-escalation": "⬆",
  "defense-evasion":      "🛡",
  "credential-access":    "🔑",
  "discovery":            "🔍",
  "lateral-movement":     "↔",
  "collection":           "📦",
  "exfiltration":         "📤",
  "impact":               "💥",
};

const PAGE_SIZE = 10;

// -- colour helpers -----------------------------------------------------------

function sevColor(sev?: string): { rgb: string; css: string } {
  if (sev === "escalate") return { rgb: "255,77,77",   css: "var(--sev-escalate)" };
  if (sev === "review")   return { rgb: "245,165,36",  css: "var(--sev-review)"   };
  return                         { rgb: "91,140,255",  css: "var(--sev-observe)"  };
}

function cellBg(count: number, sev?: string): string {
  if (count === 0) return "rgba(255,255,255,0.025)";
  const alpha = Math.min(0.12 + count * 0.06, 0.75);
  return `rgba(${sevColor(sev).rgb},${alpha})`;
}

function cellBorderColor(count: number, sev?: string): string {
  if (count === 0) return "rgba(255,255,255,0.07)";
  return `rgba(${sevColor(sev).rgb},0.45)`;
}

function cellGlow(count: number, sev?: string): string {
  if (count === 0) return "none";
  return `0 0 10px rgba(${sevColor(sev).rgb},0.22), inset 0 0 8px rgba(${sevColor(sev).rgb},0.12)`;
}

// -- sub-components -----------------------------------------------------------

/** Tooltip shown on cell hover */
const CellTooltip = memo(function CellTooltip({
  def, cell, anchorRef,
}: {
  def: TechniqueDef;
  cell?: ThreatMapCell;
  anchorRef: React.RefObject<HTMLButtonElement | null>;
}) {
  const count = cell?.count ?? 0;
  const rect  = anchorRef.current?.getBoundingClientRect();
  if (!rect) return null;

  // Position: below and centred on cell, clamped to viewport
  const left  = Math.max(8, Math.min(rect.left + rect.width / 2 - 120, window.innerWidth - 256));
  const top   = rect.bottom + 8;

  return (
    <div style={{
      position: "fixed",
      left, top,
      width: 240,
      background: "#1a1f2e",
      border: "1px solid rgba(255,255,255,0.12)",
      borderRadius: 8,
      padding: "10px 12px",
      zIndex: 200,
      pointerEvents: "none",
      boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
      animation: "fadeIn 0.1s ease",
    }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: sevColor(cell?.severity_max).css, marginBottom: 3 }}>
        {def.id}
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: "#e6ecff", marginBottom: 6 }}>
        {def.name}
      </div>
      {def.description && (
        <div style={{ fontSize: 11, color: "#9aa3bd", lineHeight: 1.45, marginBottom: 6 }}>
          {def.description.length > 120 ? def.description.slice(0, 117) + "…" : def.description}
        </div>
      )}
      <div style={{ fontSize: 11, fontWeight: 700, color: count > 0 ? sevColor(cell?.severity_max).css : "#4a5568" }}>
        {count > 0 ? `${count} hit${count !== 1 ? "s" : ""}` : "No hits"}
      </div>
    </div>
  );
});

/** Single technique cell inside the matrix */
function TechCell({
  def, cell, onClick,
}: {
  def: TechniqueDef;
  cell?: ThreatMapCell;
  onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);

  const count  = cell?.count ?? 0;
  const sev    = cell?.severity_max;
  const active = count > 0;

  return (
    <>
      <button
        ref={btnRef}
        onClick={active ? onClick : undefined}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          gap: 3,
          width: "100%",
          padding: "7px 8px",
          borderRadius: 6,
          border: `1px solid ${hovered && active
            ? `rgba(${sevColor(sev).rgb},0.75)`
            : cellBorderColor(count, sev)}`,
          background: hovered && active
            ? `rgba(${sevColor(sev).rgb},${Math.min(0.12 + count * 0.06 + 0.12, 0.88)})`
            : cellBg(count, sev),
          cursor: active ? "pointer" : "default",
          textAlign: "left",
          transition: "all 0.15s ease",
          boxShadow: hovered && active
            ? `0 0 14px rgba(${sevColor(sev).rgb},0.35), inset 0 0 10px rgba(${sevColor(sev).rgb},0.18)`
            : cellGlow(count, sev),
          transform: hovered && active ? "translateY(-1px)" : "none",
          position: "relative",
          overflow: "hidden",
          minHeight: 50,
        }}
      >
        {/* top row: ID + count badge */}
        <div style={{ display: "flex", alignItems: "center", gap: 4, width: "100%" }}>
          <span style={{
            fontFamily: "var(--font-mono)",
            fontSize: 9,
            color: active ? "#c8d3f5" : "#2d3748",
            fontWeight: active ? 600 : 400,
            letterSpacing: "0.02em",
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}>
            {def.id}
          </span>
          {active && (
            <span style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              fontWeight: 700,
              color: sevColor(sev).css,
              background: `rgba(${sevColor(sev).rgb},0.18)`,
              padding: "1px 5px",
              borderRadius: 4,
              flexShrink: 0,
            }}>
              {count}
            </span>
          )}
        </div>

        {/* technique name */}
        <span style={{
          fontSize: 9,
          color: active ? "#8a95b8" : "#1e2535",
          lineHeight: 1.3,
          maxWidth: "100%",
          overflow: "hidden",
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical" as const,
        }}>
          {def.name}
        </span>
      </button>

      {hovered && (
        <CellTooltip def={def} cell={cell} anchorRef={btnRef} />
      )}
    </>
  );
}

// -- detection drawer ---------------------------------------------------------

function DetectionDrawer({
  techniqueId,
  techniqueDef,
  tactic,
  windowSpec,
  onClose,
}: {
  techniqueId: string;
  techniqueDef: TechniqueDef;
  tactic: string;
  windowSpec: string;
  onClose: () => void;
}) {
  const navigate   = useNavigate();
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["threat-map-cell", techniqueId, windowSpec, page],
    queryFn: () =>
      api.getThreatMapCellDetections(techniqueId, {
        window: windowSpec,
        page,
        page_size: PAGE_SIZE,
      }),
    keepPreviousData: true,
  } as Parameters<typeof useQuery>[0]);

  const items: DetectionSummary[] = (data as { items?: DetectionSummary[] } | undefined)?.items ?? [];
  const total: number             = (data as { total?: number } | undefined)?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0,
          background: "rgba(0,0,0,0.55)",
          zIndex: 40,
          backdropFilter: "blur(3px)",
          animation: "fadeIn 0.15s ease",
        }}
      />

      {/* Drawer panel */}
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0,
        width: "min(500px, 100vw)",
        background: "var(--surface-panel)",
        borderLeft: "1px solid var(--surface-border)",
        zIndex: 50,
        display: "flex", flexDirection: "column",
        boxShadow: "-16px 0 48px rgba(0,0,0,0.7)",
        animation: "slideInDrawer 0.22s ease",
      }}>

        {/* Header */}
        <div style={{
          padding: "20px 24px",
          borderBottom: "1px solid var(--surface-border)",
          background: "var(--surface-panel)",
          flexShrink: 0,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{
                  fontFamily: "var(--font-mono)", fontSize: 10,
                  color: "var(--sev-observe)",
                  background: "rgba(91,140,255,0.12)",
                  padding: "2px 7px", borderRadius: 4,
                  border: "1px solid rgba(91,140,255,0.25)",
                }}>
                  {techniqueDef.id}
                </span>
                <span style={{
                  fontSize: 10, color: "#4a5568",
                  textTransform: "uppercase", letterSpacing: "0.06em",
                }}>
                  {TACTIC_LABELS[tactic] ?? tactic}
                </span>
              </div>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: "#e6ecff", margin: 0, lineHeight: 1.3 }}>
                {techniqueDef.name}
              </h3>
            </div>
            <button
              onClick={onClose}
              style={{
                background: "rgba(255,255,255,0.07)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 6,
                color: "#9aa3bd", cursor: "pointer",
                fontSize: 14, padding: "5px 10px",
                flexShrink: 0, transition: "background 0.1s",
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.12)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.07)"; }}
            >
              ✕
            </button>
          </div>
          {techniqueDef.description && (
            <p style={{
              fontSize: 12, color: "#9aa3bd",
              marginTop: 10, lineHeight: 1.5, margin: "10px 0 0",
            }}>
              {techniqueDef.description}
            </p>
          )}
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 24px" }}>
          <div style={{
            fontSize: 11, fontWeight: 600,
            textTransform: "uppercase", letterSpacing: "0.08em",
            color: "#9aa3bd", marginBottom: 12,
          }}>
            {isLoading
              ? "Loading…"
              : `${total} detection${total !== 1 ? "s" : ""}`}
          </div>

          {isLoading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div style={{
              textAlign: "center", color: "#4a5568",
              padding: "48px 0", fontSize: 13,
            }}>
              No detections in this window
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {items.map((det) => (
                <button
                  key={det.id}
                  onClick={() => navigate(`/detections/${encodeURIComponent(det.id)}`)}
                  style={{
                    display: "flex", gap: 12, alignItems: "flex-start",
                    padding: "10px 12px",
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid var(--surface-border)",
                    borderRadius: 8, cursor: "pointer",
                    textAlign: "left", width: "100%",
                    transition: "background 0.1s, border-color 0.1s",
                  }}
                  onMouseEnter={(e) => {
                    const el = e.currentTarget as HTMLElement;
                    el.style.background = "rgba(255,255,255,0.08)";
                    el.style.borderColor = "rgba(91,140,255,0.3)";
                  }}
                  onMouseLeave={(e) => {
                    const el = e.currentTarget as HTMLElement;
                    el.style.background = "rgba(255,255,255,0.04)";
                    el.style.borderColor = "var(--surface-border)";
                  }}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <SeverityChip severity={det.severity} compact />
                      <span style={{
                        fontFamily: "var(--font-mono)", fontSize: 11, color: "#e6ecff",
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      }}>
                        {det.function_id}
                      </span>
                    </div>
                    <span style={{ fontSize: 11, color: "#9aa3bd" }}>{det.anomaly_type}</span>
                  </div>
                  <span style={{
                    fontSize: 10, color: "#4a5568",
                    whiteSpace: "nowrap", flexShrink: 0, paddingTop: 2,
                  }}>
                    {formatRelativeTime(det.ingested_at)}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Pagination footer */}
        {totalPages > 1 && (
          <div style={{
            padding: "12px 24px",
            borderTop: "1px solid var(--surface-border)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
            flexShrink: 0,
          }}>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              style={{
                padding: "5px 14px", borderRadius: 6,
                border: "1px solid rgba(255,255,255,0.1)",
                background: page === 1 ? "transparent" : "rgba(255,255,255,0.06)",
                color: page === 1 ? "#2d3748" : "#9aa3bd",
                cursor: page === 1 ? "default" : "pointer",
                fontSize: 12,
              }}
            >
              ← Prev
            </button>
            <span style={{ fontSize: 11, color: "#4a5568" }}>
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              style={{
                padding: "5px 14px", borderRadius: 6,
                border: "1px solid rgba(255,255,255,0.1)",
                background: page === totalPages ? "transparent" : "rgba(255,255,255,0.06)",
                color: page === totalPages ? "#2d3748" : "#9aa3bd",
                cursor: page === totalPages ? "default" : "pointer",
                fontSize: 12,
              }}
            >
              Next →
            </button>
          </div>
        )}
      </div>

      <style>{`
        @keyframes fadeIn       { from { opacity: 0 } to { opacity: 1 } }
        @keyframes slideInDrawer { from { transform: translateX(40px); opacity: 0 } to { transform: none; opacity: 1 } }
      `}</style>
    </>
  );
}

// -- skeleton grid ------------------------------------------------------------

function MatrixSkeleton() {
  return (
    <div style={{
      overflowX: "auto",
      borderRadius: 12,
      border: "1px solid var(--surface-border)",
    }}>
      <div style={{
        display: "grid",
        gridTemplateColumns: `repeat(${TACTIC_ORDER.length}, minmax(130px, 1fr))`,
        minWidth: TACTIC_ORDER.length * 140,
        gap: 0,
      }}>
        {TACTIC_ORDER.map((t) => (
          <div key={t} style={{ borderRight: "1px solid var(--surface-border)" }}>
            {/* header skeleton */}
            <div style={{
              padding: "12px 10px",
              borderBottom: "1px solid var(--surface-border)",
              background: "rgba(255,255,255,0.02)",
            }}>
              <Skeleton className="h-5 w-full" />
            </div>
            {/* cell skeletons */}
            <div style={{ padding: 8, display: "flex", flexDirection: "column", gap: 4 }}>
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// -- main page ----------------------------------------------------------------

interface Selected {
  techniqueId: string;
  def: TechniqueDef;
  tactic: string;
}

export default function ThreatMapPage() {
  const [windowSpec, setWindowSpec] = useState("7d");
  const [selected,   setSelected]   = useState<Selected | null>(null);

  const gridQuery = useQuery({
    queryKey: ["threat-map-grid"],
    queryFn: api.getThreatMapGrid,
    staleTime: Infinity,
  });

  const mapQuery = useQuery({
    queryKey: ["threat-map", windowSpec],
    queryFn: () => api.getThreatMap({ window: windowSpec }),
    refetchInterval: 30_000,
  });

  const grid   = gridQuery.data as ThreatMapGridResponse | undefined;
  const map    = mapQuery.data  as ThreatMapResponse     | undefined;
  const matrix = map?.matrix ?? {};

  /** Ordered list of tactics that actually exist in the grid data */
  const orderedTactics = useMemo(() => {
    if (!grid) return TACTIC_ORDER.slice();
    return TACTIC_ORDER.filter((t) => grid.tactics[t] !== undefined);
  }, [grid]);

  /** Per-tactic total hit counts */
  const tacticCounts = useMemo(() =>
    Object.fromEntries(
      orderedTactics.map((t) => [
        t,
        Object.values(matrix[t] ?? {}).reduce((s, c) => s + (c.count ?? 0), 0),
      ])
    ),
    [orderedTactics, matrix]
  );

  const totalHits = useMemo(
    () => Object.values(tacticCounts).reduce((s, n) => s + n, 0),
    [tacticCounts]
  );

  const handleCellClick = useCallback(
    (tactic: string, def: TechniqueDef) => {
      const cell = matrix[tactic]?.[def.id];
      if (!cell || cell.count === 0) return;
      setSelected({ techniqueId: def.id, def, tactic });
    },
    [matrix]
  );

  const loading = gridQuery.isLoading || mapQuery.isLoading;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Page header */}
      <header style={{
        display: "flex", alignItems: "flex-end",
        justifyContent: "space-between",
        flexWrap: "wrap", gap: 12,
      }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: "#e6ecff", margin: 0 }}>
            Threat Map
          </h1>
          <p style={{ marginTop: 4, fontSize: 12, color: "#9aa3bd", margin: "4px 0 0" }}>
            MITRE ATT&amp;CK coverage&ensp;&middot;&ensp;
            <span style={{ color: totalHits > 0 ? "#e6ecff" : "#4a5568", fontWeight: totalHits > 0 ? 600 : 400 }}>
              {totalHits} hit{totalHits !== 1 ? "s" : ""}
            </span>
            {" "}in window
            {map && (
              <span style={{ marginLeft: 8, opacity: 0.45 }}>
                {new Date(map.since).toLocaleDateString()} – {new Date(map.until).toLocaleDateString()}
              </span>
            )}
          </p>
        </div>

        {/* Time window selector */}
        <div style={{
          display: "flex", gap: 4,
          background: "rgba(255,255,255,0.05)",
          borderRadius: 8, padding: 4,
        }}>
          {WINDOW_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setWindowSpec(opt.value)}
              style={{
                padding: "6px 16px", borderRadius: 6,
                border: "none", cursor: "pointer",
                fontSize: 12, fontWeight: windowSpec === opt.value ? 600 : 400,
                background: windowSpec === opt.value
                  ? "var(--surface-panel)"
                  : "transparent",
                color: windowSpec === opt.value ? "#e6ecff" : "#9aa3bd",
                boxShadow: windowSpec === opt.value
                  ? "0 1px 4px rgba(0,0,0,0.4)"
                  : "none",
                transition: "all 0.15s",
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </header>

      {/* Legend bar */}
      <div style={{
        display: "flex", gap: 20, alignItems: "center",
        fontSize: 11, color: "#9aa3bd", flexWrap: "wrap",
        padding: "10px 16px",
        background: "var(--surface-panel)",
        border: "1px solid var(--surface-border)",
        borderRadius: 8,
      }}>
        <span style={{ fontWeight: 600, color: "#4a5568", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Legend
        </span>
        {[
          { label: "No hits",  rgb: "255,255,255", alpha: 0.025, borderAlpha: 0.07 },
          { label: "Observe",  rgb: "91,140,255",  alpha: 0.35,  borderAlpha: 0.55 },
          { label: "Review",   rgb: "245,165,36",  alpha: 0.4,   borderAlpha: 0.55 },
          { label: "Escalate", rgb: "255,77,77",   alpha: 0.5,   borderAlpha: 0.65 },
        ].map((l) => (
          <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{
              width: 14, height: 14, borderRadius: 4,
              background: `rgba(${l.rgb},${l.alpha})`,
              border: `1px solid rgba(${l.rgb},${l.borderAlpha})`,
              boxShadow: l.alpha > 0.1 ? `0 0 6px rgba(${l.rgb},0.2)` : "none",
            }} />
            <span>{l.label}</span>
          </div>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 10, opacity: 0.4 }}>
          Hover a cell for details · click an active cell to drill into detections
        </span>
      </div>

      {/* Matrix */}
      {loading ? (
        <MatrixSkeleton />
      ) : grid ? (
        <div style={{
          overflowX: "auto",
          borderRadius: 12,
          border: "1px solid var(--surface-border)",
          background: "var(--surface-panel)",
          /* Let headers stick as user scrolls down */
          position: "relative",
        }}>
          <div style={{
            display: "grid",
            gridTemplateColumns: `repeat(${orderedTactics.length}, minmax(138px, 1fr))`,
            minWidth: orderedTactics.length * 148,
          }}>
            {orderedTactics.map((tactic, colIdx) => {
              const techniques  = grid.tactics[tactic] ?? [];
              const tacticTotal = tacticCounts[tactic] ?? 0;
              const hasHits     = tacticTotal > 0;
              const isLast      = colIdx === orderedTactics.length - 1;

              return (
                <div
                  key={tactic}
                  style={{
                    borderRight: isLast ? "none" : "1px solid var(--surface-border)",
                    display: "flex", flexDirection: "column",
                  }}
                >
                  {/* Sticky column header */}
                  <div style={{
                    position: "sticky", top: 0, zIndex: 10,
                    padding: "10px 10px 8px",
                    borderBottom: "1px solid var(--surface-border)",
                    background: hasHits
                      ? "rgba(91,140,255,0.06)"
                      : "rgba(255,255,255,0.02)",
                    display: "flex", flexDirection: "column",
                    alignItems: "center", gap: 4,
                    textAlign: "center",
                  }}>
                    <span style={{ fontSize: 16, lineHeight: 1 }}>
                      {TACTIC_ICONS[tactic] ?? "⬛"}
                    </span>
                    <span style={{
                      fontSize: 10, fontWeight: 600,
                      color: hasHits ? "#c8d3f5" : "#4a5568",
                      lineHeight: 1.2,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}>
                      {TACTIC_LABELS[tactic] ?? tactic}
                    </span>
                    {/* Hit count badge */}
                    <span style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11, fontWeight: 700,
                      color: hasHits ? "var(--sev-observe)" : "#2d3748",
                      background: hasHits
                        ? "rgba(91,140,255,0.15)"
                        : "rgba(255,255,255,0.04)",
                      padding: "1px 7px",
                      borderRadius: 99,
                      border: hasHits
                        ? "1px solid rgba(91,140,255,0.3)"
                        : "1px solid rgba(255,255,255,0.06)",
                      minWidth: 24,
                      display: "inline-block",
                      textAlign: "center",
                    }}>
                      {tacticTotal}
                    </span>
                  </div>

                  {/* Technique cells */}
                  <div style={{ padding: "6px 6px", display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
                    {techniques.length === 0 ? (
                      <div style={{
                        fontSize: 10, color: "#1e2535",
                        padding: "16px 0", textAlign: "center",
                      }}>
                        No techniques
                      </div>
                    ) : (
                      techniques.map((def) => (
                        <TechCell
                          key={def.id}
                          def={def}
                          cell={matrix[tactic]?.[def.id]}
                          onClick={() => handleCellClick(tactic, def)}
                        />
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {/* Right-side detection drawer */}
      {selected && (
        <DetectionDrawer
          techniqueId={selected.techniqueId}
          techniqueDef={selected.def}
          tactic={selected.tactic}
          windowSpec={windowSpec}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
