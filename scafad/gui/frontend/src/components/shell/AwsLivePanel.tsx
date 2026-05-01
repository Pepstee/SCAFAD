import { useState, useEffect, useRef, useContext } from "react";
import { api } from "@/lib/api";
import { AwsConfigContext, validatePollInterval } from "@/lib/awsConfig";
import { useAwsStream } from "@/lib/useAwsStream";
import type { AwsFunction } from "@/lib/types";

interface DetectionResult {
  id: string;
  severity: string;
  function_id: string;
}

interface PullResult {
  pulled: number;
  ingested: number;
  detections: DetectionResult[];
  errors: string[];
}

const MINUTES_OPTIONS = [15, 30, 60, 120, 240] as const;
const MAX_EVENTS_OPTIONS = [10, 25, 50, 100] as const;
const POLL_INTERVAL_OPTIONS = [1, 5, 10, 15, 30] as const; // seconds

const sevColor = (s: string) =>
  s === "escalate"
    ? "var(--sev-escalate)"
    : s === "review"
    ? "var(--sev-review)"
    : "var(--sev-observe)";

export function AwsLivePanel({ onClose }: { onClose: () => void }) {
  // ========== AWS Pull mode (legacy) ==========
  const [awsAvailable, setAwsAvailable] = useState<boolean | null>(null);
  const [awsReason, setAwsReason] = useState<string>("");
  const [region, setRegion] = useState<string>("");
  const [functions, setFunctions] = useState<AwsFunction[]>([]);
  const [selectedFn, setSelectedFn] = useState<string>("");
  const [minutesBack, setMinutesBack] = useState<number>(60);
  const [maxEvents, setMaxEvents] = useState<number>(50);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PullResult | null>(null);
  const [errorsOpen, setErrorsOpen] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [showAnomaly, setShowAnomaly] = useState<Record<string, string>>({});
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ========== AWS Stream mode (new) ==========
  const awsContext = useContext(AwsConfigContext);
  const awsStream = awsContext ? useAwsStream() : null;
  const [showSettingsDrawer, setShowSettingsDrawer] = useState(false);
  const [testLatency, setTestLatency] = useState<number | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testSuccess, setTestSuccess] = useState<boolean | null>(null);

  // Fetch functions on mount (legacy mode)
  useEffect(() => {
    api
      .awsFunctions()
      .then((data) => {
        if (data.available === false) {
          setAwsAvailable(false);
          setAwsReason(data.reason ?? "AWS not configured");
        } else {
          setAwsAvailable(true);
          setRegion(data.region ?? "");
          setFunctions(data.functions ?? []);
          if (data.functions && data.functions.length > 0) {
            setSelectedFn(data.functions[0].name);
          }
        }
      })
      .catch((err: unknown) => {
        setAwsAvailable(false);
        setAwsReason(String(err));
      });
  }, []);

  // Auto-refresh handler (legacy mode)
  useEffect(() => {
    if (autoRefresh && selectedFn) {
      intervalRef.current = setInterval(() => {
        void doPull();
      }, 60_000);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, selectedFn, minutesBack, maxEvents]);

  const doPull = async () => {
    if (!selectedFn || loading) return;
    setLoading(true);
    setResult(null);
    setErrorsOpen(false);
    try {
      const data = await api.awsPull({
        function_name: selectedFn,
        minutes_back: minutesBack,
        max_events: maxEvents,
      });
      setResult(data);
      // Build anomaly map for display
      const anomalyMap: Record<string, string> = {};
      data.detections.forEach((d) => {
        anomalyMap[d.id] = d.severity;
      });
      setShowAnomaly(anomalyMap);
    } catch (err: unknown) {
      setResult({
        pulled: 0,
        ingested: 0,
        detections: [],
        errors: [String(err)],
      });
    } finally {
      setLoading(false);
    }
  };

  const severityCount = (sev: string) =>
    result?.detections.filter((d) => d.severity === sev).length ?? 0;

  // ========== Test Connection ==========
  const handleTestConnection = async () => {
    if (!awsStream) return;
    setTestLoading(true);
    try {
      const { latency_ms, success } = await awsStream.testConnection();
      setTestLatency(latency_ms);
      setTestSuccess(success);
      setTimeout(() => setTestSuccess(null), 3000);
    } finally {
      setTestLoading(false);
    }
  };

  // ========== Settings drawer content ==========
  const renderSettingsDrawer = () => {
    if (!awsContext || !awsStream) return null;

    const { config } = awsContext;
    const pollIntervalSecs = config.pollIntervalMs / 1000;

    return (
      <>
        {/* Backdrop */}
        <div
          onClick={() => setShowSettingsDrawer(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.55)",
            zIndex: 60,
            backdropFilter: "blur(3px)",
            animation: "fadeIn 0.15s",
          }}
        />

        {/* Settings drawer (slides in from right of main panel) */}
        <div
          style={{
            position: "fixed",
            top: 0,
            right: "min(440px, 100vw)",
            bottom: 0,
            width: "min(360px, 100vw)",
            background: "var(--surface-panel)",
            borderLeft: "1px solid var(--surface-border)",
            zIndex: 70,
            display: "flex",
            flexDirection: "column",
            boxShadow: "-12px 0 48px rgba(0,0,0,0.7)",
            animation: "slideIn 0.2s ease",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "20px 24px",
              borderBottom: "1px solid var(--surface-border)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h3 style={{ fontSize: 15, fontWeight: 600, color: "#e6ecff", margin: 0 }}>
              AWS Settings
            </h3>
            <button
              onClick={() => setShowSettingsDrawer(false)}
              style={{
                background: "rgba(255,255,255,0.07)",
                border: "none",
                borderRadius: 6,
                color: "#9aa3bd",
                cursor: "pointer",
                fontSize: 16,
                padding: "4px 10px",
              }}
            >
              ✕
            </button>
          </div>

          {/* Settings content */}
          <div
            style={{
              padding: "20px 24px",
              display: "flex",
              flexDirection: "column",
              gap: 16,
              flex: 1,
              overflowY: "auto",
            }}
          >
            {/* Region */}
            <div>
              <label
                style={{
                  fontSize: 11,
                  color: "#9aa3bd",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  display: "block",
                  marginBottom: 6,
                }}
              >
                AWS Region
              </label>
              <input
                type="text"
                value={config.region}
                onChange={(e) =>
                  awsContext.setConfig({ region: e.target.value })
                }
                placeholder="e.g., eu-west-1"
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: 7,
                  border: "1px solid var(--surface-border)",
                  background: "rgba(255,255,255,0.05)",
                  color: "#e6ecff",
                  fontSize: 13,
                  fontFamily: "var(--font-mono)",
                }}
              />
            </div>

            {/* Function prefix */}
            <div>
              <label
                style={{
                  fontSize: 11,
                  color: "#9aa3bd",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  display: "block",
                  marginBottom: 6,
                }}
              >
                Function Prefix
              </label>
              <input
                type="text"
                value={config.functionPrefix}
                onChange={(e) =>
                  awsContext.setConfig({ functionPrefix: e.target.value })
                }
                placeholder="e.g., prod-"
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: 7,
                  border: "1px solid var(--surface-border)",
                  background: "rgba(255,255,255,0.05)",
                  color: "#e6ecff",
                  fontSize: 13,
                  fontFamily: "var(--font-mono)",
                }}
              />
            </div>

            {/* Poll interval */}
            <div>
              <div
                style={{
                  fontSize: 11,
                  color: "#9aa3bd",
                  marginBottom: 6,
                  display: "flex",
                  justifyContent: "space-between",
                }}
              >
                <span
                  style={{
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}
                >
                  Poll Interval
                </span>
                <span
                  style={{ fontFamily: "var(--font-mono)", color: "#e6ecff" }}
                >
                  {pollIntervalSecs}s
                </span>
              </div>
              <input
                type="range"
                min={1}
                max={30}
                step={1}
                value={pollIntervalSecs}
                onChange={(e) =>
                  awsContext.setConfig({
                    pollIntervalMs: validatePollInterval(
                      Number(e.target.value) * 1000
                    ),
                  })
                }
                style={{ width: "100%", accentColor: "#7aa2ff" }}
              />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginTop: 2,
                }}
              >
                <span
                  style={{ fontSize: 9, color: "#4a5568", fontFamily: "var(--font-mono)" }}
                >
                  1s
                </span>
                <span
                  style={{ fontSize: 9, color: "#4a5568", fontFamily: "var(--font-mono)" }}
                >
                  30s
                </span>
              </div>
            </div>

            {/* Enable toggle */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <label
                style={{
                  fontSize: 11,
                  color: "#9aa3bd",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                }}
              >
                Live Polling
              </label>
              <button
                onClick={() =>
                  awsContext.setConfig({ enabled: !config.enabled })
                }
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid var(--surface-border)",
                  background: config.enabled
                    ? "rgba(34,197,94,0.15)"
                    : "rgba(255,255,255,0.03)",
                  color: config.enabled ? "#22c55e" : "#9aa3bd",
                  cursor: "pointer",
                  fontSize: 12,
                  fontWeight: 600,
                }}
              >
                {config.enabled ? "Enabled" : "Disabled"}
              </button>
            </div>

            {/* Test connection button */}
            <button
              onClick={handleTestConnection}
              disabled={testLoading}
              style={{
                padding: "10px 14px",
                borderRadius: 8,
                border: "1px solid var(--surface-border)",
                background: "rgba(122,162,255,0.15)",
                color: "#7aa2ff",
                cursor: testLoading ? "not-allowed" : "pointer",
                fontSize: 13,
                fontWeight: 600,
                transition: "all 0.15s",
              }}
            >
              {testLoading ? "Testing..." : "Test Connection"}
            </button>

            {/* Test result */}
            {testSuccess !== null && (
              <div
                style={{
                  padding: "10px 12px",
                  borderRadius: 6,
                  background: testSuccess
                    ? "rgba(34,197,94,0.1)"
                    : "rgba(248,113,113,0.1)",
                  border: `1px solid ${
                    testSuccess ? "rgba(34,197,94,0.3)" : "rgba(248,113,113,0.3)"
                  }`,
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    color: testSuccess ? "#22c55e" : "#f87171",
                    fontWeight: 600,
                  }}
                >
                  {testSuccess ? "✓ Connected" : "✗ Failed"}
                </div>
                {testLatency !== null && (
                  <div
                    style={{
                      fontSize: 11,
                      color: "#9aa3bd",
                      marginTop: 4,
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    Latency: {testLatency}ms
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </>
    );
  };

  return (
    <>
      {/* Main AWS Live Panel */}
      <div
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.55)",
          zIndex: 40,
          backdropFilter: "blur(3px)",
          animation: "fadeIn 0.15s",
        }}
        onClick={onClose}
      />

      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "min(440px, 100vw)",
          background: "var(--surface-panel)",
          borderLeft: "1px solid var(--surface-border)",
          zIndex: 50,
          display: "flex",
          flexDirection: "column",
          boxShadow: "-12px 0 48px rgba(0,0,0,0.7)",
          animation: "slideIn 0.2s ease",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "20px 24px",
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
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: awsStream?.isLive ? "#22c55e" : "#4a5568",
                  boxShadow: awsStream?.isLive ? "0 0 8px #22c55e" : "none",
                  animation: awsStream?.isLive ? "pulse 2s infinite" : "none",
                }}
              />
              <h3
                style={{
                  fontSize: 15,
                  fontWeight: 600,
                  color: "#e6ecff",
                  margin: 0,
                }}
              >
                AWS Live Ingest
              </h3>
            </div>
            <p style={{ fontSize: 11, color: "#9aa3bd", margin: "4px 0 0" }}>
              {awsStream?.isLive
                ? `Streaming at ${awsStream.eventsPerMinute} events/min`
                : "CloudWatch → SCAFAD detection pipeline"}
            </p>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {awsContext && (
              <button
                onClick={() => setShowSettingsDrawer(!showSettingsDrawer)}
                style={{
                  background: "rgba(255,255,255,0.07)",
                  border: "none",
                  borderRadius: 6,
                  color: "#9aa3bd",
                  cursor: "pointer",
                  fontSize: 14,
                  padding: "4px 10px",
                  fontWeight: 600,
                }}
                title="Settings"
              >
                ⚙
              </button>
            )}
            <button
              onClick={onClose}
              style={{
                background: "rgba(255,255,255,0.07)",
                border: "none",
                borderRadius: 6,
                color: "#9aa3bd",
                cursor: "pointer",
                fontSize: 16,
                padding: "4px 10px",
              }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Body */}
        <div
          style={{
            padding: "20px 24px",
            display: "flex",
            flexDirection: "column",
            gap: 16,
            flex: 1,
            overflowY: "auto",
          }}
        >
          {/* Show stream mode if available, otherwise legacy mode */}
          {awsStream && (
            <>
              {/* Stream Status */}
              {awsStream.error && (
                <div
                  style={{
                    background: "rgba(248,113,113,0.06)",
                    border: "1px solid rgba(248,113,113,0.3)",
                    borderRadius: 8,
                    padding: "12px 14px",
                  }}
                >
                  <div style={{ color: "#f87171", fontSize: 12 }}>
                    {awsStream.error}
                  </div>
                </div>
              )}

              {/* Event stream log */}
              {awsStream.events.length > 0 && (
                <div>
                  <div
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      color: "#9aa3bd",
                      marginBottom: 6,
                    }}
                  >
                    Recent events ({awsStream.events.length})
                  </div>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                      maxHeight: 300,
                      overflowY: "auto",
                    }}
                  >
                    {awsStream.events.slice(0, 20).map((evt, i) => (
                      <div
                        key={`${evt.id}-${i}`}
                        style={{
                          display: "flex",
                          gap: 8,
                          alignItems: "center",
                          padding: "6px 10px",
                          background: "rgba(255,255,255,0.03)",
                          border: "1px solid var(--surface-border)",
                          borderRadius: 6,
                          animation: i === 0 ? "fadeIn 0.2s" : "none",
                          fontSize: 11,
                        }}
                      >
                        <span
                          style={{
                            fontSize: 9,
                            fontWeight: 700,
                            color: sevColor(evt.severity),
                            background: `${sevColor(evt.severity)}22`,
                            borderRadius: 4,
                            padding: "1px 5px",
                            flexShrink: 0,
                            textTransform: "uppercase",
                          }}
                        >
                          {evt.severity}
                        </span>
                        <span
                          style={{
                            fontFamily: "var(--font-mono)",
                            color: "#e6ecff",
                            flex: 1,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {evt.function_name}
                        </span>
                        {evt.anomaly_score !== undefined && (
                          <span
                            style={{
                              fontSize: 9,
                              color: "#9aa3bd",
                              fontFamily: "var(--font-mono)",
                            }}
                          >
                            {evt.anomaly_score.toFixed(3)}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Empty state */}
              {awsStream.events.length === 0 && !awsStream.error && (
                <div
                  style={{
                    textAlign: "center",
                    padding: "40px 20px",
                    color: "#9aa3bd",
                    fontSize: 12,
                  }}
                >
                  {awsContext?.config.enabled
                    ? "Waiting for events..."
                    : "Enable polling in settings to receive events"}
                </div>
              )}
            </>
          )}

          {/* Legacy AWS Pull Mode */}
          {!awsStream && (
            <>
              {/* AWS status section */}
              <div
                style={{
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid var(--surface-border)",
                  borderRadius: 8,
                  padding: "12px 14px",
                }}
              >
                {awsAvailable === null && (
                  <div style={{ color: "#9aa3bd", fontSize: 12 }}>
                    Checking AWS connectivity...
                  </div>
                )}
                {awsAvailable === true && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <div
                      style={{
                        fontSize: 11,
                        color: "#22c55e",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                      }}
                    >
                      Connected
                    </div>
                    <div style={{ fontSize: 12, color: "#e6ecff" }}>
                      Region:{" "}
                      <span style={{ fontFamily: "var(--font-mono)" }}>
                        {region}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: "#9aa3bd" }}>
                      {functions.length} Lambda function
                      {functions.length !== 1 ? "s" : ""} discovered
                    </div>
                  </div>
                )}
                {awsAvailable === false && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <div
                      style={{
                        fontSize: 11,
                        color: "#ff4d4d",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                      }}
                    >
                      AWS not configured
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: "#9aa3bd",
                        fontFamily: "var(--font-mono)",
                        wordBreak: "break-word",
                      }}
                    >
                      {awsReason}
                    </div>
                    <div style={{ fontSize: 11, color: "#6b7280", marginTop: 4 }}>
                      Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and
                      AWS_DEFAULT_REGION environment variables, then restart the
                      backend.
                    </div>
                  </div>
                )}
              </div>

              {/* Function selector */}
              {awsAvailable && functions.length > 0 && (
                <div>
                  <label
                    style={{
                      fontSize: 11,
                      color: "#9aa3bd",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                      display: "block",
                      marginBottom: 6,
                    }}
                  >
                    Lambda Function
                  </label>
                  <select
                    value={selectedFn}
                    onChange={(e) => setSelectedFn(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: 7,
                      border: "1px solid var(--surface-border)",
                      background: "rgba(255,255,255,0.05)",
                      color: "#e6ecff",
                      fontSize: 13,
                      fontFamily: "var(--font-mono)",
                      cursor: "pointer",
                      appearance: "none",
                    }}
                  >
                    {functions.map((fn) => (
                      <option key={fn.name} value={fn.name}>
                        {fn.name} ({fn.runtime})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Minutes back slider */}
              <div>
                <div
                  style={{
                    fontSize: 11,
                    color: "#9aa3bd",
                    marginBottom: 6,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span
                    style={{
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                    }}
                  >
                    Look-back window
                  </span>
                  <span
                    style={{ fontFamily: "var(--font-mono)", color: "#e6ecff" }}
                  >
                    {minutesBack}m
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={MINUTES_OPTIONS.length - 1}
                  step={1}
                  value={MINUTES_OPTIONS.indexOf(minutesBack as typeof MINUTES_OPTIONS[number])}
                  onChange={(e) =>
                    setMinutesBack(MINUTES_OPTIONS[Number(e.target.value)])
                  }
                  style={{ width: "100%", accentColor: "#22c55e" }}
                />
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginTop: 2,
                  }}
                >
                  {MINUTES_OPTIONS.map((m) => (
                    <span
                      key={m}
                      style={{
                        fontSize: 9,
                        color: m === minutesBack ? "#22c55e" : "#4a5568",
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      {m}m
                    </span>
                  ))}
                </div>
              </div>

              {/* Max events selector */}
              <div>
                <label
                  style={{
                    fontSize: 11,
                    color: "#9aa3bd",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    display: "block",
                    marginBottom: 6,
                  }}
                >
                  Max events
                </label>
                <div style={{ display: "flex", gap: 6 }}>
                  {MAX_EVENTS_OPTIONS.map((n) => (
                    <button
                      key={n}
                      onClick={() => setMaxEvents(n)}
                      style={{
                        flex: 1,
                        padding: "6px 0",
                        borderRadius: 6,
                        border: "1px solid var(--surface-border)",
                        cursor: "pointer",
                        fontSize: 12,
                        fontFamily: "var(--font-mono)",
                        fontWeight: n === maxEvents ? 700 : 400,
                        background:
                          n === maxEvents
                            ? "rgba(34,197,94,0.15)"
                            : "rgba(255,255,255,0.03)",
                        color: n === maxEvents ? "#22c55e" : "#9aa3bd",
                        transition: "all 0.12s",
                      }}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>

              {/* Action buttons */}
              <div style={{ display: "flex", gap: 10 }}>
                <button
                  onClick={() => void doPull()}
                  disabled={loading || !awsAvailable || !selectedFn}
                  style={{
                    flex: 2,
                    padding: "10px",
                    borderRadius: 8,
                    border: "none",
                    cursor:
                      loading || !awsAvailable || !selectedFn
                        ? "not-allowed"
                        : "pointer",
                    background:
                      loading || !awsAvailable || !selectedFn
                        ? "rgba(255,255,255,0.04)"
                        : "rgba(34,197,94,0.15)",
                    color:
                      loading || !awsAvailable || !selectedFn
                        ? "#4a5568"
                        : "#22c55e",
                    fontSize: 13,
                    fontWeight: 600,
                    transition: "all 0.15s",
                  }}
                >
                  {loading ? (
                    <span
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 6,
                      }}
                    >
                      <span
                        style={{
                          display: "inline-block",
                          width: 12,
                          height: 12,
                          border: "2px solid #22c55e",
                          borderTopColor: "transparent",
                          borderRadius: "50%",
                          animation: "spin 0.7s linear infinite",
                        }}
                      />
                      Pulling...
                    </span>
                  ) : (
                    "☁ Pull from AWS"
                  )}
                </button>
                <button
                  onClick={() => setAutoRefresh((v) => !v)}
                  disabled={!awsAvailable || !selectedFn}
                  style={{
                    flex: 1,
                    padding: "10px",
                    borderRadius: 8,
                    border: "none",
                    cursor: !awsAvailable || !selectedFn ? "not-allowed" : "pointer",
                    background: autoRefresh
                      ? "rgba(34,197,94,0.2)"
                      : "rgba(255,255,255,0.04)",
                    color: autoRefresh ? "#22c55e" : "#6b7280",
                    fontSize: 12,
                    fontWeight: 600,
                    transition: "all 0.15s",
                  }}
                >
                  {autoRefresh ? "⏹ Stop" : "↻ Auto"}
                </button>
              </div>
              {autoRefresh && (
                <div
                  style={{
                    fontSize: 10,
                    color: "#22c55e",
                    textAlign: "center",
                    animation: "pulse 2s infinite",
                  }}
                >
                  Auto-refreshing every 60s
                </div>
              )}

              {/* Results */}
              {result && (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                    animation: "fadeIn 0.2s",
                  }}
                >
                  {/* Summary row */}
                  <div
                    style={{
                      background: "rgba(34,197,94,0.07)",
                      border: "1px solid rgba(34,197,94,0.2)",
                      borderRadius: 8,
                      padding: "10px 14px",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 13,
                        color: "#e6ecff",
                        fontWeight: 600,
                      }}
                    >
                      Pulled {result.pulled} events &rarr; {result.ingested}{" "}
                      detection{result.ingested !== 1 ? "s" : ""}
                    </div>
                    {result.ingested > 0 && (
                      <div
                        style={{
                          display: "flex",
                          gap: 12,
                          marginTop: 6,
                          fontSize: 11,
                        }}
                      >
                        {(["escalate", "review", "observe"] as const).map(
                          (sev) => (
                            <span
                              key={sev}
                              style={{
                                color: sevColor(sev),
                                fontFamily: "var(--font-mono)",
                              }}
                            >
                              {severityCount(sev)}{" "}
                              <span style={{ color: "#6b7280" }}>{sev}</span>
                            </span>
                          )
                        )}
                      </div>
                    )}
                  </div>

                  {/* Detection list */}
                  {result.detections.length > 0 && (
                    <div>
                      <div
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "0.08em",
                          color: "#9aa3bd",
                          marginBottom: 6,
                        }}
                      >
                        New detections (top {Math.min(10, result.detections.length)})
                      </div>
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: 4,
                          maxHeight: 260,
                          overflowY: "auto",
                        }}
                      >
                        {result.detections.slice(0, 10).map((d, i) => (
                          <div
                            key={d.id}
                            style={{
                              display: "flex",
                              gap: 8,
                              alignItems: "center",
                              padding: "6px 10px",
                              background: "rgba(255,255,255,0.03)",
                              border: "1px solid var(--surface-border)",
                              borderRadius: 6,
                              animation: i === 0 ? "fadeIn 0.2s" : "none",
                            }}
                          >
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 700,
                                color: sevColor(d.severity),
                                background: `${sevColor(d.severity)}22`,
                                borderRadius: 4,
                                padding: "1px 5px",
                                flexShrink: 0,
                                textTransform: "uppercase",
                              }}
                            >
                              {d.severity}
                            </span>
                            <span
                              style={{
                                fontFamily: "var(--font-mono)",
                                fontSize: 11,
                                color: "#e6ecff",
                                flex: 1,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {d.function_id}
                            </span>
                            <span
                              style={{
                                fontSize: 9,
                                color: "#4a5568",
                                fontFamily: "var(--font-mono)",
                                flexShrink: 0,
                              }}
                            >
                              {d.id.slice(0, 8)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Errors section */}
                  {result.errors.length > 0 && (
                    <div>
                      <button
                        onClick={() => setErrorsOpen((v) => !v)}
                        style={{
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          fontSize: 11,
                          color: "#f87171",
                          fontWeight: 600,
                          padding: 0,
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        {errorsOpen ? "▾" : "▸"} {result.errors.length} error
                        {result.errors.length !== 1 ? "s" : ""}
                      </button>
                      {errorsOpen && (
                        <div
                          style={{
                            marginTop: 6,
                            display: "flex",
                            flexDirection: "column",
                            gap: 4,
                            maxHeight: 160,
                            overflowY: "auto",
                          }}
                        >
                          {result.errors.map((err, i) => (
                            <div
                              key={i}
                              style={{
                                fontSize: 10,
                                color: "#f87171",
                                fontFamily: "var(--font-mono)",
                                padding: "4px 8px",
                                background: "rgba(248,113,113,0.06)",
                                borderRadius: 5,
                                wordBreak: "break-word",
                              }}
                            >
                              {err}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Settings drawer (when open) */}
      {showSettingsDrawer && renderSettingsDrawer()}

      <style>{`
        @keyframes fadeIn  { from { opacity: 0 } to { opacity: 1 } }
        @keyframes slideIn { from { transform: translateX(32px); opacity: 0 } to { transform: none; opacity: 1 } }
        @keyframes pulse   { 0%,100% { opacity:1 } 50% { opacity:0.4 } }
        @keyframes spin    { to { transform: rotate(360deg) } }
      `}</style>
    </>
  );
}
