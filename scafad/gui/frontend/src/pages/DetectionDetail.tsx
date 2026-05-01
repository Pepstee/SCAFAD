import { useMemo, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api, queryKeys } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SeverityChip } from "@/components/ui/SeverityChip";
import { Skeleton } from "@/components/ui/Skeleton";
import { DataTable, ColumnDef } from "@/components/ui/DataTable";
import { KPI } from "@/components/ui/KPI";
import { formatTimestamp, severityColorVar, clsx } from "@/lib/format";
import type { DetectionDetail, Severity } from "@/lib/types";

const TABS = [
  { id: "l0", label: "L0 Detectors", color: "#5b8cff" },
  { id: "l1", label: "L1 Quality", color: "#a78bfa" },
  { id: "l2", label: "L2 Matrix", color: "#06b6d4" },
  { id: "l3", label: "L3 Fusion", color: "#f59e0b" },
  { id: "l4", label: "L4 Rationale", color: "#10b981" },
  { id: "l5", label: "L5 MITRE", color: "#ef4444" },
  { id: "raw", label: "Raw JSON", color: "#6b7280" },
] as const;

type TabId = (typeof TABS)[number]["id"];

const LIFECYCLE_STAGES = [
  { id: "created", label: "Created" },
  { id: "enriched", label: "Enriched" },
  { id: "scored", label: "Scored" },
  { id: "classified", label: "Classified" },
  { id: "resolved", label: "Resolved" },
] as const;

export default function DetectionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<TabId>("l0");

  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.detection(id ?? ""),
    queryFn: () => api.getDetection(id!),
    enabled: !!id,
    staleTime: 30_000,
  });

  if (!id) {
    return (
      <Card title="Missing detection id">
        <p className="text-sm text-surface-muted">Open a detection from the dashboard.</p>
      </Card>
    );
  }

  if (isLoading) {
    return <DetectionSkeleton />;
  }

  if (error || !data) {
    return (
      <Card title="Detection not found">
        <p className="text-sm text-surface-muted">
          {error?.message ?? "The requested detection does not exist."}
        </p>
        <Link
          to="/"
          className="mt-3 inline-block rounded-md border border-surface-border px-3 py-1.5 text-sm text-ink hover:bg-surface-subtle"
        >
          ← Back to dashboard
        </Link>
      </Card>
    );
  }

  const shortId = data.id.slice(0, 8);

  return (
    <div className="flex flex-col gap-4">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-surface-muted">
        <Link to="/" className="text-ink-accent hover:underline">
          ← Dashboard
        </Link>
        <span>/</span>
        <span>Detection {shortId}</span>
      </nav>

      {/* Timeline strip */}
      <TimelineStrip severity={data.severity} />

      {/* Main content: two-column layout */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_0.55fr]">
        {/* Left column: Header + Tabbed inspector */}
        <div className="flex flex-col gap-4">
          {/* Enhanced header with animated severity badge */}
          <DetailHeader data={data} />

          {/* Pill-style tab bar with color coding */}
          <TabBar tabs={TABS} activeTab={tab} onChange={setTab} />

          {/* Tab content */}
          <div data-testid="detection-tab-panel">
            {tab === "l0" && <L0Panel data={data} />}
            {tab === "l1" && <L1Panel data={data} />}
            {tab === "l2" && <L2Panel data={data} />}
            {tab === "l3" && <L3Panel data={data} />}
            {tab === "l4" && <L4Panel data={data} />}
            {tab === "l5" && <L5Panel data={data} />}
            {tab === "raw" && <RawPanel data={data} />}
          </div>
        </div>

        {/* Right column: Persistent context panel */}
        <ContextPanel data={data} />
      </div>
    </div>
  );
}

/**
 * Skeleton loader matching the two-column layout
 */
function DetectionSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-24 w-full" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_0.55fr]">
        <div className="flex flex-col gap-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
        <Skeleton className="h-[600px] w-full" />
      </div>
    </div>
  );
}

/**
 * Enhanced header with animated glow pulse based on severity
 */
function DetailHeader({ data }: { data: DetectionDetail }) {
  const severity = data.severity as Severity;
  const glowColor = severityColorVar(severity);

  // Get pulse animation based on severity
  const pulseClass = {
    observe: "animate-glow-pulse-observe",
    review: "animate-glow-pulse-review",
    escalate: "animate-glow-pulse-escalate",
  }[severity] || "animate-pulse";

  return (
    <Card>
      <div className="flex flex-col gap-4">
        {/* Severity badge with glow pulse */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className={`inline-block rounded-full border-2 p-3 ${pulseClass}`}
              style={{ borderColor: glowColor, boxShadow: `0 0 12px ${glowColor}40` }}>
              <SeverityChip severity={severity} />
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs uppercase tracking-wider text-surface-muted">Trust fused score</div>
            <div className="text-4xl font-bold tabular-nums text-ink">
              {data.trust_score.toFixed(3)}
            </div>
          </div>
        </div>

        {/* Function name as main title */}
        <div>
          <h1 className="font-mono text-lg font-semibold text-ink">{data.function_id}</h1>
          <p className="mt-1 text-xs text-surface-muted">
            {data.anomaly_type}
            {data.risk_band && <> · Risk: {data.risk_band}</>}
            {data.decision && <> · {data.decision}</>}
          </p>
        </div>

        {/* Metadata row */}
        <div className="flex flex-wrap items-center gap-3 border-t border-surface-border pt-3 text-xs text-surface-muted">
          <span>Event ID: <span className="font-mono text-ink-dim">{data.event_id.slice(0, 12)}…</span></span>
          <span>•</span>
          <span>Ingested {formatTimestamp(data.ingested_at)}</span>
        </div>
      </div>
    </Card>
  );
}

/**
 * Pill-style tab bar with layer color coding
 */
function TabBar({
  tabs,
  activeTab,
  onChange,
}: {
  tabs: readonly (typeof TABS)[number][];
  activeTab: TabId;
  onChange: (tab: TabId) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2 rounded-lg bg-surface-subtle p-2">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id as TabId)}
          className={clsx(
            "px-3 py-2 text-xs font-medium rounded-full transition-all whitespace-nowrap",
            activeTab === t.id
              ? "text-white shadow-lg"
              : "text-surface-muted hover:text-ink"
          )}
          style={
            activeTab === t.id
              ? {
                  background: t.color,
                  boxShadow: `0 0 12px ${t.color}40`,
                }
              : { color: "var(--ink-dim)" }
          }
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Timeline strip showing detection lifecycle
 */
function TimelineStrip({ severity }: { severity: Severity }) {
  const color = severityColorVar(severity);
  const completedStages = LIFECYCLE_STAGES.slice(0, 4); // Typically all stages complete by viewing

  return (
    <Card>
      <div className="flex items-center gap-3">
        {completedStages.map((stage, idx) => (
          <div key={stage.id} className="flex items-center gap-3">
            <div className="flex flex-col items-center gap-1">
              <div
                className="h-3 w-3 rounded-full"
                style={{ background: color }}
              />
              <span className="text-xs text-surface-muted">{stage.label}</span>
            </div>
            {idx < completedStages.length - 1 && (
              <div
                className="h-0.5 w-8"
                style={{ background: color }}
              />
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

/**
 * Persistent right-side context panel with MITRE, case linkage, quick actions
 */
function ContextPanel({ data }: { data: DetectionDetail }) {
  const onCopyFingerprint = useCallback(() => {
    // Simple fingerprint: hash of key attributes
    const fingerprint = `${data.event_id}-${data.function_id}-${data.anomaly_type}`;
    navigator.clipboard.writeText(fingerprint);
  }, [data]);

  return (
    <div className="flex flex-col gap-4">
      {/* Quick Actions */}
      <Card title="Quick Actions" className="flex flex-col gap-3">
        <button className="rounded-md border border-surface-border bg-surface-subtle px-3 py-2 text-xs font-medium text-ink hover:bg-surface-border transition-colors">
          + Create Case
        </button>
        <button className="rounded-md border border-surface-border bg-surface-subtle px-3 py-2 text-xs font-medium text-ink hover:bg-surface-border transition-colors">
          Mark as False Positive
        </button>
        <button className="rounded-md border border-surface-border bg-surface-subtle px-3 py-2 text-xs font-medium text-ink hover:bg-surface-border transition-colors">
          Suppress Alert
        </button>
      </Card>

      {/* Case Linkage */}
      {data.case && (
        <Card title="Linked Case" className="flex flex-col gap-2">
          <div className="text-sm">
            <div className="font-mono text-ink-accent">{data.case.id}</div>
            <div className="text-xs text-surface-muted">{data.case.title}</div>
            <Badge tone="info" className="mt-2 inline-block">
              {data.case.status}
            </Badge>
          </div>
        </Card>
      )}

      {/* MITRE Techniques as clickable pills */}
      {data.mitre_techniques.length > 0 && (
        <Card title="MITRE Techniques" className="flex flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            {data.mitre_techniques.map((technique) => (
              <a
                key={technique}
                href={`https://attack.mitre.org/techniques/${technique.replace(/\./g, "/")}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-full bg-[rgba(255,77,77,0.12)] px-2 py-1 text-[11px] font-medium text-[#ffb8b8] hover:bg-[rgba(255,77,77,0.25)] transition-colors"
              >
                {technique}
                <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            ))}
          </div>
        </Card>
      )}

      {/* Detection Fingerprint */}
      <Card title="Detection Fingerprint" className="flex flex-col gap-2">
        <div className="font-mono text-xs text-ink-dim break-all">
          {data.event_id}
        </div>
        <button
          onClick={onCopyFingerprint}
          className="w-full rounded-md border border-surface-border bg-surface-subtle px-2 py-1.5 text-xs font-medium text-ink hover:bg-surface-border transition-colors flex items-center justify-center gap-1"
        >
          <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          Copy
        </button>
      </Card>

      {/* KPI Summary */}
      <KPI label="Layer Confidence" value={`${(data.trust_score * 100).toFixed(0)}%`} />
    </div>
  );
}

interface DetectorVote {
  detector: string;
  score: number;
  confidence: number;
  rationale: string;
}

/**
 * L0 Tab: Detector votes as horizontal bar chart + table
 */
function L0Panel({ data }: { data: DetectionDetail }) {
  const layer2 = data.layer_payload.multilayer_result.layer2 as Record<string, unknown>;
  const signals = (layer2.signals as Array<Record<string, unknown>>) ?? [];
  const layer0 = data.layer_payload.layer0_record as Record<string, unknown>;
  const summary = (layer0.custom_fields as Record<string, unknown>) ?? {};

  const rows: DetectorVote[] = useMemo(
    () =>
      signals.map((s) => ({
        detector: String(s.detector_name ?? "unknown"),
        score: Number(s.score ?? 0),
        confidence: Number(s.confidence ?? 0),
        rationale: String(s.rationale ?? ""),
      })),
    [signals]
  );

  const columns: ColumnDef<DetectorVote>[] = [
    {
      key: "detector",
      header: "Detector",
      render: (r) => <span className="font-mono text-xs">{r.detector}</span>,
    },
    {
      key: "score",
      header: "Score",
      align: "right",
      render: (r) => <span className="font-mono text-xs tabular-nums">{r.score.toFixed(3)}</span>,
    },
    {
      key: "confidence",
      header: "Confidence",
      align: "right",
      render: (r) => <span className="font-mono text-xs tabular-nums">{r.confidence.toFixed(3)}</span>,
    },
    {
      key: "rationale",
      header: "Rationale",
      render: (r) => <span className="text-xs text-surface-muted">{r.rationale}</span>,
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      {/* Horizontal bar chart visualization */}
      <Card title="Detector Votes (Visual)" description="Score distribution across detectors">
        <div className="space-y-2">
          {rows.map((r) => (
            <div key={r.detector} className="flex items-center gap-2">
              <span className="w-24 text-xs font-mono text-ink-dim">{r.detector.slice(0, 20)}</span>
              <div className="flex-1 h-6 bg-surface-subtle rounded-md overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-sev-observe to-sev-escalate transition-all"
                  style={{ width: `${Math.min(100, r.score * 100)}%` }}
                />
              </div>
              <span className="w-12 text-right text-xs font-mono text-ink">{r.score.toFixed(2)}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Summary */}
      <Card title="L0 Enrichment Summary" description="Top-level detector confidence">
        <pre className="font-mono whitespace-pre-wrap text-xs text-ink overflow-auto max-h-64">
          {JSON.stringify(summary.l0_detection_summary ?? summary, null, 2)}
        </pre>
      </Card>

      {/* Data table */}
      <Card title="Detector Votes (Table)" description="Per-detector signals">
        <DataTable rows={rows} columns={columns} rowKey={(r) => r.detector} emptyState="No detector signals" />
      </Card>
    </div>
  );
}

/**
 * L1 Tab: Privacy and sanitisation audit
 */
function L1Panel({ data }: { data: DetectionDetail }) {
  const layer1 = data.layer_payload.layer1_record as Record<string, unknown>;
  const quality = (layer1.quality_report as Record<string, unknown>) ?? {};
  const audit = (layer1.audit_record as Record<string, unknown>) ?? {};

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Card title="Quality Report" description="L1 sanitiser self-report">
        <pre className="font-mono whitespace-pre-wrap text-xs text-ink overflow-auto max-h-96">
          {JSON.stringify(quality, null, 2)}
        </pre>
      </Card>
      <Card title="Audit Record" description="Validation, sanitisation, privacy, hashing">
        <pre className="font-mono whitespace-pre-wrap text-xs text-ink overflow-auto max-h-96">
          {JSON.stringify(audit, null, 2)}
        </pre>
      </Card>
    </div>
  );
}

/**
 * L2 Tab: Multi-vector detection matrix
 */
function L2Panel({ data }: { data: DetectionDetail }) {
  const layer2 = data.layer_payload.multilayer_result.layer2 as Record<string, unknown>;

  return (
    <Card
      title="L2 Multi-Vector Detection Matrix"
      description="Aggregate score, anomaly indication, per-detector signals"
    >
      <SyntaxHighlightedJSON data={layer2} />
    </Card>
  );
}

interface FusionWeight {
  detector: string;
  weight: number;
}

/**
 * L3 Tab: Trust-weighted fusion with optional radar visualization
 */
function L3Panel({ data }: { data: DetectionDetail }) {
  const layer3 = data.layer_payload.multilayer_result.layer3 as Record<string, unknown>;
  const weights = (layer3.trust_weights as Record<string, number>) ?? {};

  const weightRows: FusionWeight[] = useMemo(
    () =>
      Object.entries(weights).map(([detector, weight]) => ({
        detector,
        weight: Number(weight),
      })),
    [weights]
  );

  const columns: ColumnDef<FusionWeight>[] = [
    {
      key: "detector",
      header: "Detector",
      render: (r) => <span className="font-mono text-xs">{r.detector}</span>,
    },
    {
      key: "weight",
      header: "Weight",
      align: "right",
      render: (r) => <span className="font-mono text-xs tabular-nums">{r.weight.toFixed(3)}</span>,
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <Card title="Trust-Weighted Fusion" description="L3 fused score, risk band, volatility">
        <div className="grid grid-cols-2 gap-4 text-sm mb-4">
          <KPI label="Fused Score" value={Number(layer3.fused_score ?? 0).toFixed(3)} />
          <KPI label="Risk Band" value={String(layer3.risk_band ?? "—")} />
        </div>
        <div className="border-t border-surface-border pt-4">
          <SyntaxHighlightedJSON
            data={{
              fused_score: layer3.fused_score,
              risk_band: layer3.risk_band,
              consensus_strength: layer3.consensus_strength,
              trust_score_input: layer3.trust_score_input,
              volatility_adjustment: layer3.volatility_adjustment,
            }}
          />
        </div>
      </Card>

      <Card title="Trust Weights" description="Per-detector contribution to fused score">
        <DataTable rows={weightRows} columns={columns} rowKey={(r) => r.detector} emptyState="No weights" />
      </Card>
    </div>
  );
}

interface SHAPContribution {
  feature: string;
  contribution: number;
}

/**
 * L4 Tab: SHAP rationale with horizontal bars (positive=green, negative=red)
 */
function L4Panel({ data }: { data: DetectionDetail }) {
  const layer4 = data.layer_payload.multilayer_result.layer4 as Record<string, unknown>;
  const points = (layer4.explanation_points as string[]) ?? [];
  const shapValues = (layer4.shap_values as Record<string, number>) ?? {};

  const shapContributions: SHAPContribution[] = useMemo(
    () =>
      Object.entries(shapValues)
        .map(([feature, value]) => ({
          feature,
          contribution: Number(value),
        }))
        .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)),
    [shapValues]
  );

  return (
    <div className="flex flex-col gap-4">
      <Card title="Decision Summary" description="L4 explainability trace">
        <dl className="grid grid-cols-2 gap-4 text-sm mb-4">
          <Field label="Decision">{String(layer4.decision ?? "—")}</Field>
          <Field label="Severity">{String(layer4.severity ?? "—")}</Field>
          <Field label="Verbosity">{String(layer4.verbosity ?? "—")}</Field>
          <Field label="Recommended Action">{String(layer4.recommended_action ?? "—")}</Field>
        </dl>
        {layer4.explanation_summary ? (
          <div className="border-t border-surface-border pt-4">
            <p className="text-sm text-ink">{String(layer4.explanation_summary)}</p>
          </div>
        ) : null}
      </Card>

      {/* SHAP Feature Contributions as horizontal bars */}
      {shapContributions.length > 0 && (
        <Card title="Feature Contributions (SHAP)" description="Positive (green) and negative (red) contributions">
          <div className="space-y-3">
            {shapContributions.slice(0, 10).map((sc) => {
              const isPositive = sc.contribution > 0;
              const maxVal = Math.max(...shapContributions.map((x) => Math.abs(x.contribution)));
              const barWidth = Math.min(100, (Math.abs(sc.contribution) / maxVal) * 100);

              return (
                <div key={sc.feature} className="flex items-center gap-2">
                  <span className="w-32 truncate text-xs font-mono text-ink-dim">{sc.feature}</span>
                  <div className="flex-1 h-5 bg-surface-subtle rounded-sm overflow-hidden flex items-center">
                    {isPositive ? (
                      <div
                        className="h-full bg-gradient-to-r from-green-900 to-green-600"
                        style={{ width: `${barWidth}%` }}
                      />
                    ) : (
                      <div
                        className="ml-auto h-full bg-gradient-to-r from-red-600 to-red-900"
                        style={{ width: `${barWidth}%` }}
                      />
                    )}
                  </div>
                  <span className="w-16 text-right text-xs font-mono text-ink">
                    {sc.contribution > 0 ? "+" : ""}{sc.contribution.toFixed(3)}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Explanation points */}
      <Card title="Explanation Points" description="Detector-level contributions to decision">
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink">
          {points.length === 0 && <li className="text-surface-muted">No explanation points</li>}
          {points.map((p, idx) => (
            <li key={idx}>{p}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

/**
 * L5 Tab: MITRE techniques as rich cards with external links
 */
function L5Panel({ data }: { data: DetectionDetail }) {
  const layer5 = data.layer_payload.multilayer_result.layer5 as Record<string, unknown>;
  const techniques = (layer5.techniques as string[]) ?? [];
  const tactics = (layer5.tactics as string[]) ?? [];
  const techDetails = (layer5.technique_details as Array<{
    id: string;
    name: string;
    tactic: string;
    description: string;
    confidence?: number;
  }>) ?? [];
  const story = (layer5.attack_story as string) ?? "";

  return (
    <div className="flex flex-col gap-4">
      {/* Rich MITRE cards */}
      {techDetails.length > 0 ? (
        <Card title="MITRE ATT&CK Techniques" description="Detailed technique breakdown">
          <div className="grid grid-cols-1 gap-3">
            {techDetails.map((tech) => (
              <div
                key={tech.id}
                className="rounded-lg border border-surface-border bg-surface-subtle p-3 hover:border-ink-accent transition-colors"
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div>
                    <a
                      href={`https://attack.mitre.org/techniques/${tech.id.replace(/\./g, "/")}/`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-sm font-semibold text-ink-accent hover:underline flex items-center gap-1"
                    >
                      {tech.id}
                      <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                    <h3 className="text-xs font-semibold text-ink mt-0.5">{tech.name}</h3>
                  </div>
                  {tech.confidence !== undefined && (
                    <Badge tone="info" className="whitespace-nowrap">
                      {(tech.confidence * 100).toFixed(0)}%
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-surface-muted mb-2">{tech.description}</p>
                <Badge tone="warn" className="text-[10px]">{tech.tactic}</Badge>
              </div>
            ))}
          </div>
        </Card>
      ) : (
        <Card title="MITRE ATT&CK Alignment" description="Techniques and tactics inferred by L5">
          <div className="flex flex-wrap gap-2">
            {techniques.length === 0 && (
              <span className="text-sm text-surface-muted">No techniques mapped</span>
            )}
            {techniques.map((t) => (
              <a
                key={t}
                href={`https://attack.mitre.org/techniques/${t.replace(/\./g, "/")}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-mono rounded-full bg-[rgba(255,77,77,0.12)] px-2 py-1 text-[11px] font-medium text-[#ffb8b8] hover:bg-[rgba(255,77,77,0.25)] transition-colors"
              >
                {t}
                <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            ))}
          </div>
          {tactics.length > 0 && (
            <div className="mt-4 border-t border-surface-border pt-4">
              <div className="text-xs uppercase tracking-wider text-surface-muted mb-2">Tactics</div>
              <div className="flex flex-wrap gap-2">
                {tactics.map((t) => (
                  <Badge key={t} tone="warn">
                    {t}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Attack story narrative */}
      {story && (
        <Card title="Attack Story" description="Composed narrative from threat alignment">
          <p className="text-sm text-ink leading-relaxed">{story}</p>
        </Card>
      )}
    </div>
  );
}

/**
 * Raw JSON Tab: Syntax-highlighted JSON with copy-to-clipboard
 */
function RawPanel({ data }: { data: DetectionDetail }) {
  const [copied, setCopied] = useState(false);

  const onCopy = useCallback(() => {
    navigator.clipboard.writeText(JSON.stringify(data.layer_payload, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [data.layer_payload]);

  return (
    <Card
      title="Raw Evidence Payload"
      description="Full CanonicalRuntimeResult.to_dict() output"
      actions={
        <button
          onClick={onCopy}
          className="flex items-center gap-1 rounded-md border border-surface-border bg-surface-subtle px-2 py-1 text-xs font-medium text-ink hover:bg-surface-border transition-colors"
        >
          <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          {copied ? "Copied!" : "Copy"}
        </button>
      }
    >
      <SyntaxHighlightedJSON data={data.layer_payload} />
    </Card>
  );
}

/**
 * Syntax-highlighted JSON renderer with CSS classes for syntax coloring
 */
function SyntaxHighlightedJSON({ data }: { data: unknown }) {
  const jsonStr = JSON.stringify(data, null, 2);
  const rendered = renderJSON(jsonStr);

  return (
    <pre className="font-mono text-xs overflow-auto max-h-96 rounded-md bg-surface-subtle p-3 text-ink">
      <code>{rendered as React.ReactNode[]}</code>
    </pre>
  );
}

/**
 * Simple JSON syntax highlighting using React spans
 */
function renderJSON(json: string): Array<React.ReactNode | string> {
  const regex = /("(?:\\.|[^"\\])*")|(\d+\.\d+|\d+)|(\btrue\b|\bfalse\b|\bnull\b)|([{}[\]:,])/g;

  const result: Array<React.ReactNode | string> = [];
  let lastIndex = 0;
  let matchIndex = 0;

  json.replace(regex, (match: string, str: string | undefined, num: string | undefined, bool: string | undefined, punct: string | undefined, offset: number) => {
    if (offset > lastIndex) {
      result.push(json.substring(lastIndex, offset));
    }

    if (str) {
      // String (check if it's a key)
      const isKey = json[offset - 1] !== ":" && json.substring(offset + match.length).match(/^\s*:/);
      result.push(
        <span key={matchIndex++} style={{ color: isKey ? "#7aa2ff" : "#7ad9a3" }}>
          {match}
        </span>
      );
    } else if (num) {
      // Number
      result.push(
        <span key={matchIndex++} style={{ color: "#f5a524" }}>
          {match}
        </span>
      );
    } else if (bool) {
      // Boolean/null
      result.push(
        <span key={matchIndex++} style={{ color: "#a78bfa" }}>
          {match}
        </span>
      );
    } else if (punct) {
      // Punctuation
      result.push(
        <span key={matchIndex++} style={{ color: "#9aa3bd" }}>
          {match}
        </span>
      );
    }

    lastIndex = offset + match.length;
    return match;
  });

  if (lastIndex < json.length) {
    result.push(json.substring(lastIndex));
  }

  return result;
}

/**
 * Field label component for metadata display
 */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] uppercase tracking-wider text-surface-muted">
        {label}
      </span>
      <span className="text-sm text-ink">{children}</span>
    </div>
  );
}
