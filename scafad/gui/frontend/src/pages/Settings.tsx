import React, { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api, queryKeys } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type {
  SettingsResponse,
  RuntimeRuntimeConfig,
  RedactionPolicy,
  GUIConfigSnapshot,
  DetectorEntry,
} from "@/lib/types";

/**
 * SettingsPage v2: Interactive settings hub with AWS configuration,
 * detector tuning, and policy management.
 */

// UI state for individual detector card expansion
type DetectorCardState = Record<string, boolean>;

// AWS settings form state (for demo UI, not wired to backend)
interface AWSFormState {
  region: string;
  lambdaPrefix: string;
  credentialsProfile: string;
}

export default function SettingsPage(): React.ReactElement {
  const settings = useQuery({
    queryKey: queryKeys.settings,
    queryFn: () => api.getSettings(),
    refetchInterval: 60_000,
  });

  // Tab navigation
  const tabs = [
    { id: "runtime", label: "Runtime", icon: "⚙️" },
    { id: "aws", label: "AWS", icon: "☁️" },
    { id: "policy", label: "Policy", icon: "🔒" },
    { id: "redaction", label: "Redaction", icon: "✂️" },
    { id: "gui", label: "GUI", icon: "🎨" },
  ];

  const [activeTab, setActiveTab] = useState<string>("runtime");
  const [expandedDetectors, setExpandedDetectors] = useState<DetectorCardState>({});
  const [awsForm, setAWSForm] = useState<AWSFormState>({
    region: "us-east-1",
    lambdaPrefix: "prod-*",
    credentialsProfile: "default",
  });
  const [connectionStatus, setConnectionStatus] = useState<
    "idle" | "testing" | "connected" | "error"
  >("idle");

  const testConnectionMutation = useMutation({
    mutationFn: async () => {
      const response = await api.health();
      return response;
    },
    onSuccess: () => {
      setConnectionStatus("connected");
      setTimeout(() => setConnectionStatus("idle"), 3000);
    },
    onError: () => {
      setConnectionStatus("error");
      setTimeout(() => setConnectionStatus("idle"), 3000);
    },
  });

  const handleTestConnection = async () => {
    setConnectionStatus("testing");
    testConnectionMutation.mutate();
  };

  const toggleDetectorExpand = (detectorId: string) => {
    setExpandedDetectors((prev) => ({
      ...prev,
      [detectorId]: !prev[detectorId],
    }));
  };

  const handleAWSFormChange = (
    field: keyof AWSFormState,
    value: string
  ) => {
    setAWSForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const data = settings.data;

  const getConnectionColor = (): string => {
    if (connectionStatus === "connected") return "bg-green-500";
    if (connectionStatus === "error") return "bg-red-500";
    return "bg-gray-600";
  };

  return (
    <div className="flex h-full gap-0">
      {/* Left Sidebar Navigation */}
      <div className="w-48 border-r border-surface-border bg-surface-subtle flex flex-col">
        <div className="p-4 border-b border-surface-border">
          <h2 className="text-sm font-bold text-ink tracking-wide">Settings</h2>
        </div>

        <nav className="flex-1 overflow-y-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? "bg-surface-panel border-l-2 border-ink-accent text-ink"
                  : "border-l-2 border-transparent text-surface-muted hover:text-ink hover:bg-surface-panel"
              }`}
            >
              <span className="text-lg">{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-auto">
        <div className="border-b border-surface-border bg-surface-subtle px-6 py-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-ink-dim">ℹ️</span>
            <p className="text-xs text-ink-dim">
              Some settings require backend restart to take effect
            </p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {settings.isLoading && (
            <div className="text-sm text-surface-muted">Loading settings...</div>
          )}

          {settings.isError && (
            <div className="rounded bg-red-50 border border-red-300 p-3 text-sm text-red-700">
              Error loading settings. Please try refreshing.
            </div>
          )}

          {data && (
            <div className="max-w-4xl">
              {activeTab === "runtime" && (
                <RuntimeTab
                  data={data}
                  expandedDetectors={expandedDetectors}
                  onToggleExpand={toggleDetectorExpand}
                />
              )}

              {activeTab === "aws" && (
                <AWSTab
                  form={awsForm}
                  onFormChange={handleAWSFormChange}
                  onTestConnection={handleTestConnection}
                  connectionStatus={connectionStatus}
                  getConnectionColor={getConnectionColor}
                  isLoading={testConnectionMutation.isPending}
                />
              )}

              {activeTab === "policy" && (
                <PolicyTab data={data} />
              )}

              {activeTab === "redaction" && (
                <RedactionTab data={data} />
              )}

              {activeTab === "gui" && (
                <GUITab data={data} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// Runtime Tab Component
// -------------------------------------------------------------------------

interface RuntimeTabProps {
  data: SettingsResponse;
  expandedDetectors: Record<string, boolean>;
  onToggleExpand: (detectorId: string) => void;
}

function RuntimeTab({
  data,
  expandedDetectors,
  onToggleExpand,
}: RuntimeTabProps): React.ReactElement {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({
    detectors: false,
    fusion: false,
  });

  const toggleSection = (section: string) => {
    setCollapsed((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  return (
    <div className="space-y-6">
      <div>
        <div
          className="flex items-center gap-2 cursor-pointer pb-3 border-b border-surface-border"
          onClick={() => toggleSection("detectors")}
        >
          <span className="text-sm font-semibold text-ink">Detector Algorithms</span>
          <span className={`text-xs text-surface-muted transition-transform ${collapsed.detectors ? "" : "rotate-180"}`}>
            ▼
          </span>
        </div>

        {!collapsed.detectors && (
          <div className="mt-4 grid grid-cols-1 gap-3">
            {!data.runtime.available ? (
              <div className="text-sm text-surface-muted italic py-4">
                Runtime not yet warmed
              </div>
            ) : (
              data.runtime.detector_panel.detectors.map((detector: DetectorEntry) => (
                <div
                  key={detector.id}
                  className="rounded border border-surface-border bg-surface-panel p-4 hover:border-ink-accent transition-colors"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-mono text-sm font-semibold text-ink">
                          {detector.id}
                        </h3>
                        <Badge tone="info">
                          {getDetectorType(detector.id)}
                        </Badge>
                      </div>
                      <p className="text-xs text-surface-muted mb-3">
                        Weight: {detector.weight.toFixed(2)}
                        {detector.threshold !== null
                          ? ` | Threshold: ${detector.threshold.toFixed(3)}`
                          : ""}
                      </p>

                      {expandedDetectors[detector.id] && (
                        <div className="space-y-2">
                          <div className="text-xs text-ink-dim">
                            Weight adjustment (visual only)
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.01"
                            defaultValue={String(detector.weight)}
                            className="w-full cursor-pointer"
                            disabled
                          />
                          <div className="text-xs text-surface-muted">
                            Current: {(detector.weight * 100).toFixed(1)}%
                          </div>
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => onToggleExpand(detector.id)}
                      className="text-xs text-ink-accent hover:text-ink-default transition-colors px-2 py-1"
                    >
                      {expandedDetectors[detector.id] ? "▲" : "▼"}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      <div>
        <div
          className="flex items-center gap-2 cursor-pointer pb-3 border-b border-surface-border"
          onClick={() => toggleSection("fusion")}
        >
          <span className="text-sm font-semibold text-ink">Layer Fusion Weights</span>
          <span className={`text-xs text-surface-muted transition-transform ${collapsed.fusion ? "" : "rotate-180"}`}>
            ▼
          </span>
        </div>

        {!collapsed.fusion && (
          <div className="mt-4 space-y-2">
            {Object.entries(data.runtime.fusion.layer_weights).map(
              ([layer, weight]: [string, number]) => (
                <div
                  key={layer}
                  className="flex items-center justify-between py-2 px-3 rounded bg-surface-subtle border border-surface-border text-sm"
                >
                  <span className="text-ink-dim">{layer}</span>
                  <code className="text-ink-accent font-mono">
                    {(weight as number).toFixed(3)}
                  </code>
                </div>
              )
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// AWS Tab Component
// -------------------------------------------------------------------------

interface AWSTabProps {
  form: AWSFormState;
  onFormChange: (field: keyof AWSFormState, value: string) => void;
  onTestConnection: () => void;
  connectionStatus: string;
  getConnectionColor: () => string;
  isLoading: boolean;
}

function AWSTab({
  form,
  onFormChange,
  onTestConnection,
  connectionStatus,
  getConnectionColor,
  isLoading,
}: AWSTabProps): React.ReactElement {
  return (
    <div className="space-y-6">
      <Card title="AWS Configuration" description="Configure AWS Lambda integration">
        <div className="space-y-4">
          <div className="flex items-center gap-3 pb-4 border-b border-surface-border">
            <div className={`w-3 h-3 rounded-full ${getConnectionColor()} animate-pulse`} />
            <span className="text-xs text-surface-muted">
              {connectionStatus === "idle" && "Ready to test connection"}
              {connectionStatus === "testing" && "Testing connection..."}
              {connectionStatus === "connected" && "Connection successful"}
              {connectionStatus === "error" && "Connection failed"}
            </span>
          </div>

          <div>
            <label className="block text-xs font-semibold text-ink-dim mb-2">
              AWS Region
            </label>
            <input
              type="text"
              value={form.region}
              onChange={(e) => onFormChange("region", e.target.value)}
              className="w-full px-3 py-2 rounded border border-surface-border bg-surface-subtle text-ink text-sm focus:border-ink-accent focus:outline-none transition-colors"
              placeholder="e.g., us-east-1"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-ink-dim mb-2">
              Lambda Function Filter
            </label>
            <input
              type="text"
              value={form.lambdaPrefix}
              onChange={(e) => onFormChange("lambdaPrefix", e.target.value)}
              className="w-full px-3 py-2 rounded border border-surface-border bg-surface-subtle text-ink text-sm focus:border-ink-accent focus:outline-none transition-colors"
              placeholder="e.g., prod-*"
            />
            <p className="text-xs text-surface-muted mt-1">
              Use wildcards (*) to filter function names
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-ink-dim mb-2">
              AWS Credentials Profile
            </label>
            <input
              type="text"
              value={form.credentialsProfile}
              onChange={(e) => onFormChange("credentialsProfile", e.target.value)}
              className="w-full px-3 py-2 rounded border border-surface-border bg-surface-subtle text-ink text-sm focus:border-ink-accent focus:outline-none transition-colors"
              placeholder="e.g., default"
            />
          </div>

          <button
            onClick={onTestConnection}
            disabled={isLoading}
            className="w-full px-4 py-2 rounded bg-ink-accent text-surface-base font-medium text-sm hover:bg-opacity-90 disabled:opacity-50 transition-all"
          >
            {isLoading ? "Testing..." : "Test Connection"}
          </button>
        </div>
      </Card>

      <Card title="Configuration Summary" description="Current AWS settings">
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between py-1 border-b border-surface-border pb-1">
            <span className="text-surface-muted">Region</span>
            <code className="text-ink-accent">{form.region}</code>
          </div>
          <div className="flex items-center justify-between py-1 border-b border-surface-border pb-1">
            <span className="text-surface-muted">Lambda Filter</span>
            <code className="text-ink-accent">{form.lambdaPrefix}</code>
          </div>
          <div className="flex items-center justify-between py-1">
            <span className="text-surface-muted">Profile</span>
            <code className="text-ink-accent">{form.credentialsProfile}</code>
          </div>
        </div>
      </Card>
    </div>
  );
}

// -------------------------------------------------------------------------
// Policy Tab Component
// -------------------------------------------------------------------------

interface PolicyTabProps {
  data: SettingsResponse;
}

function PolicyTab({ data }: PolicyTabProps): React.ReactElement {
  return (
    <div className="space-y-6">
      <Card title="Retention Policy" description="Data retention settings">
        <div className="space-y-3 text-sm">
          <div>
            <h4 className="text-xs font-semibold text-ink-dim mb-2">
              Retention Period
            </h4>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-ink">
                {data.policy.retention_days}
              </span>
              <span className="text-surface-muted">days</span>
            </div>
          </div>
          <p className="text-xs text-surface-muted italic">
            Records are automatically purged after this period
          </p>
        </div>
      </Card>

      {data.policy.rules.length > 0 && (
        <Card title="Redaction Rules" description="Configured redaction policies">
          <pre className="bg-surface-subtle p-3 rounded text-xs overflow-x-auto border border-surface-border text-ink-dim font-mono">
            {JSON.stringify(data.policy.rules, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  );
}

// -------------------------------------------------------------------------
// Redaction Tab Component
// -------------------------------------------------------------------------

interface RedactionTabProps {
  data: SettingsResponse;
}

function RedactionTab({ data }: RedactionTabProps): React.ReactElement {
  const redactionFields = [
    { id: "email", label: "Email Addresses", enabled: true },
    { id: "phone", label: "Phone Numbers", enabled: true },
    { id: "ssn", label: "Social Security Numbers", enabled: true },
    { id: "credit_card", label: "Credit Card Numbers", enabled: true },
    { id: "api_keys", label: "API Keys", enabled: false },
    { id: "passwords", label: "Passwords", enabled: false },
    { id: "ips", label: "IP Addresses", enabled: true },
    { id: "names", label: "Full Names", enabled: false },
  ];

  return (
    <div className="space-y-6">
      <Card title="Redaction Policies" description="PII redaction configuration (read-only)">
        <div className="space-y-3">
          {redactionFields.map((field) => (
            <div
              key={field.id}
              className="flex items-center justify-between py-2 px-3 rounded border border-surface-border bg-surface-subtle"
            >
              <label className="flex items-center gap-3 flex-1 cursor-pointer">
                <div className="relative inline-flex h-5 w-9 items-center rounded-full bg-surface-border">
                  {field.enabled && (
                    <div className="inline-block h-4 w-4 transform rounded-full bg-green-500 transition-transform translate-x-4" />
                  )}
                  {!field.enabled && (
                    <div className="inline-block h-4 w-4 transform rounded-full bg-surface-muted transition-transform translate-x-0.5" />
                  )}
                </div>
                <span className={`text-sm font-medium ${field.enabled ? "text-ink" : "text-ink-dim"}`}>
                  {field.label}
                </span>
              </label>
              <span className={`text-xs ${field.enabled ? "text-green-400" : "text-surface-muted"}`}>
                {field.enabled ? "Enabled" : "Disabled"}
              </span>
            </div>
          ))}
        </div>
      </Card>

      <div className="rounded border border-surface-border bg-surface-subtle p-4">
        <p className="text-xs text-surface-muted">
          <span className="font-semibold">Note:</span> Redaction policies are locked in Phase 4. Phase 5 will enable dynamic configuration.
        </p>
      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// GUI Tab Component
// -------------------------------------------------------------------------

interface GUITabProps {
  data: SettingsResponse;
}

function GUITab({ data }: GUITabProps): React.ReactElement {
  const severityColors = [
    { name: "Observe", color: "#5b8cff", hex: "var(--sev-observe)" },
    { name: "Review", color: "#f5a524", hex: "var(--sev-review)" },
    { name: "Escalate", color: "#ff4d4d", hex: "var(--sev-escalate)" },
  ];

  return (
    <div className="space-y-6">
      <Card title="Severity Color Palette" description="Risk indicator color scheme">
        <div className="grid grid-cols-3 gap-4">
          {severityColors.map((sev) => (
            <div key={sev.name} className="text-center">
              <div
                className="h-20 rounded mb-2 border border-surface-border"
                style={{ backgroundColor: sev.color }}
              />
              <h4 className="text-sm font-semibold text-ink">{sev.name}</h4>
              <code className="text-xs text-surface-muted">{sev.color}</code>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Application Settings" description="Current GUI configuration">
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-xs text-surface-muted block mb-1">Environment</span>
              <code className="text-ink-accent">{data.gui.env}</code>
            </div>
            <div>
              <span className="text-xs text-surface-muted block mb-1">Version</span>
              <code className="text-ink-accent">{data.gui.version}</code>
            </div>
            <div>
              <span className="text-xs text-surface-muted block mb-1">Host</span>
              <code className="text-ink-accent">{data.gui.host}</code>
            </div>
            <div>
              <span className="text-xs text-surface-muted block mb-1">Port</span>
              <code className="text-ink-accent">{data.gui.port}</code>
            </div>
          </div>
          <div className="border-t border-surface-border pt-3">
            <span className="text-xs text-surface-muted block mb-1">SSE Keepalive</span>
            <code className="text-ink-accent">{data.gui.sse_keepalive_seconds}s</code>
          </div>
          <div className="border-t border-surface-border pt-3">
            <span className="text-xs text-surface-muted block mb-1">CORS Origins</span>
            <code className="text-ink-accent text-xs">
              {data.gui.cors_origins.length} origin(s) configured
            </code>
            {data.gui.cors_origins.length > 0 && (
              <ul className="text-xs text-surface-muted mt-2 space-y-1">
                {data.gui.cors_origins.map((origin: string) => (
                  <li key={origin} className="font-mono">
                    • {origin}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </Card>

      <Card title="Refresh Settings" description="UI polling configuration">
        <div className="space-y-3">
          <div>
            <h4 className="text-xs font-semibold text-ink-dim mb-2">
              Detection Auto-Refresh Interval
            </h4>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-ink">60</span>
              <span className="text-surface-muted">seconds</span>
            </div>
            <p className="text-xs text-surface-muted mt-1">
              Dashboard updates every 60 seconds
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

// -------------------------------------------------------------------------
// Helper Functions
// -------------------------------------------------------------------------

function getDetectorType(detectorId: string): string {
  const typeMap: Record<string, string> = {
    isolation_forest: "IsoForest",
    ocsvm: "OCSVM",
    autoencoder: "Autoencoder",
    robust_covariance: "Robust Cov",
    lof: "LOF",
    elliptic_envelope: "Elliptic",
  };

  for (const [key, label] of Object.entries(typeMap)) {
    if (detectorId.toLowerCase().includes(key)) {
      return label;
    }
  }

  return "Custom";
}
