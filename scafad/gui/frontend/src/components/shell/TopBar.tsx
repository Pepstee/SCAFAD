import { useContext, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { api, queryKeys } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { EnvBadge } from "./EnvBadge";
import { AwsConfigContext } from "@/lib/awsConfig";
import { useAwsStream } from "@/lib/useAwsStream";

const BREADCRUMB_MAP: Record<string, string[]> = {
  "/": ["Operations"],
  "/inbox": ["Inbox", "Triage"],
  "/cases": ["Cases", "Investigations"],
  "/functions": ["Functions", "Fleet inventory"],
  "/threat-map": ["Threat Map", "MITRE ATT&CK"],
  "/system": ["System Status", "Health & latency"],
  "/settings": ["Settings", "Detection tuning"],
  "/audit": ["Audit", "Immutable trail"],
};

export function TopBar() {
  const location = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [searchInput, setSearchInput] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.health,
    queryFn: api.health,
    staleTime: 60_000,
  });

  const awsContext = useContext(AwsConfigContext);
  const [awsPanelOpen, setAwsPanelOpen] = useState(false);

  // Use hook only if in context
  const awsStream = awsContext ? useAwsStream() : null;

  // Track scroll for glassmorphism effect
  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const getAwsStatusColor = () => {
    if (!awsStream) return "gray";
    if (awsStream.error) return "red";
    if (awsStream.isLive) return "green";
    return "gray";
  };

  const getAwsStatusText = () => {
    if (!awsStream) return "AWS Disconnected";
    if (awsStream.error) return "AWS Error";
    if (awsStream.isLive) return "AWS Live";
    return "AWS Disconnected";
  };

  const breadcrumbs = BREADCRUMB_MAP[location.pathname] || ["Operations"];

  return (
    <>
      <header
        className={`flex h-14 items-center justify-between border-b border-surface-border px-6 transition-all duration-200 ${
          scrolled ? "glass-panel" : "bg-surface-panel"
        }`}
      >
        <div className="flex items-center gap-4 flex-1">
          {/* Breadcrumb */}
          <nav className="flex items-center gap-2 text-sm">
            {breadcrumbs.map((crumb, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className={idx === 0 ? "font-semibold text-ink" : "text-ink-dim"}>
                  {crumb}
                </span>
                {idx < breadcrumbs.length - 1 && (
                  <span className="text-surface-border">/</span>
                )}
              </div>
            ))}
          </nav>

          {/* Global search input */}
          <div className="ml-auto mr-4 hidden sm:block">
            <input
              type="text"
              placeholder="Search cases, events..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-48 rounded-md border border-surface-border bg-surface-subtle px-3 py-1 text-xs text-ink placeholder-surface-muted transition-colors focus:border-ink-accent focus:outline-none focus:ring-1 focus:ring-ink-accent"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          {isLoading ? (
            <Skeleton className="h-5 w-32" />
          ) : (
            <>
              <EnvBadge env={data?.env ?? "dev"} />
              <span className="hidden sm:inline rounded border border-surface-border px-2 py-0.5 font-mono text-[11px] text-surface-muted">
                v{data?.version ?? "?"} @ {data?.commit ?? "?"}
              </span>

              {/* AWS Status Pill */}
              {awsStream && (
                <button
                  onClick={() => setAwsPanelOpen(!awsPanelOpen)}
                  className="flex items-center gap-2 rounded-full border border-surface-border px-3 py-1 text-xs font-medium transition-all duration-150 hover:bg-surface-subtle focus:outline-2 focus:outline-offset-2 focus:outline-ink-accent"
                  style={{
                    color:
                      getAwsStatusColor() === "green"
                        ? "#22c55e"
                        : getAwsStatusColor() === "red"
                          ? "#ff4d4d"
                          : "#9aa3bd",
                  }}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background:
                        getAwsStatusColor() === "green"
                          ? "#22c55e"
                          : getAwsStatusColor() === "red"
                            ? "#ff4d4d"
                            : "#4a5568",
                      animation:
                        getAwsStatusColor() === "green"
                          ? "pulse 2s infinite"
                          : "none",
                    }}
                  />
                  {getAwsStatusText()}
                </button>
              )}

              <div
                className="grid h-8 w-8 place-items-center rounded-full border border-surface-border bg-surface-subtle text-xs font-semibold text-ink transition-colors hover:bg-[rgba(91,140,255,0.15)] cursor-pointer"
                title="analyst@scafad.local"
                tabIndex={0}
                role="button"
              >
                AN
              </div>
            </>
          )}
        </div>
      </header>

      {/* AWS Live Panel trigger would be handled by parent component */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </>
  );
}
