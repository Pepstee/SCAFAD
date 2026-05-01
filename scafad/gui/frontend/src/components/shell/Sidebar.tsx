import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import { useState } from "react";
import { clsx } from "@/lib/format";
import { api, queryKeys } from "@/lib/api";

const NAV: Array<{
  to: string;
  label: string;
  hint?: string;
  comingSoon?: boolean;
  icon: string;
  showOpenCaseBadge?: boolean;
}> = [
  { to: "/", label: "Operations", hint: "Dashboard", icon: "□" },
  { to: "/inbox", label: "Inbox", hint: "Triage", icon: "◇" },
  { to: "/cases", label: "Cases", hint: "Investigations", icon: "▣", showOpenCaseBadge: true },
  { to: "/functions", label: "Functions", hint: "Fleet inventory", comingSoon: true, icon: "▤" },
  { to: "/threat-map", label: "Threat Map", hint: "MITRE ATT&CK", comingSoon: true, icon: "✦" },
  { to: "/system", label: "System Status", hint: "Health & latency", icon: "▲" },
  { to: "/settings", label: "Settings", hint: "Detection tuning", icon: "⚙" },
  { to: "/audit", label: "Audit", hint: "Immutable trail", icon: "≡" },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  const openCases = useQuery({
    queryKey: queryKeys.cases({ status: "open" }),
    queryFn: () => api.listCases({ status: "open", page_size: 1 }),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  const openCaseCount = openCases.data?.total ?? 0;

  return (
    <aside
      className={clsx(
        "flex shrink-0 flex-col border-r border-surface-border bg-surface-panel transition-all duration-200",
        collapsed ? "w-16" : "w-60"
      )}
    >
      <div className="flex items-center justify-between border-b border-surface-border px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-[rgba(91,140,255,0.15)] text-ink-accent">
            <span aria-hidden className="text-sm font-bold">
              S
            </span>
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="text-sm font-semibold tracking-wide text-ink">SCAFAD</span>
              <span className="text-[11px] uppercase tracking-wider text-surface-muted">
                Analyst Console
              </span>
            </div>
          )}
        </div>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="rounded p-1 text-ink-dim transition-colors hover:bg-surface-subtle hover:text-ink focus:outline-2 focus:outline-offset-2 focus:outline-ink-accent"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-label="Toggle sidebar"
        >
          {collapsed ? "▶" : "◀"}
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="space-y-0.5">
          {NAV.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  clsx(
                    "group flex items-center justify-between gap-3 rounded-md px-3 py-2 text-sm transition-all duration-150",
                    isActive
                      ? "bg-[rgba(91,140,255,0.18)] text-ink ring-1 ring-[rgba(91,140,255,0.3)]"
                      : "text-ink-dim hover:bg-[rgba(91,140,255,0.08)] hover:text-ink"
                  )
                }
              >
                <span className="flex items-center gap-3">
                  <span aria-hidden className="text-base text-ink-accent">
                    {item.icon}
                  </span>
                  {!collapsed && (
                    <span className="flex flex-col">
                      <span className="font-medium">{item.label}</span>
                      {item.hint && (
                        <span className="text-[11px] text-surface-muted">{item.hint}</span>
                      )}
                    </span>
                  )}
                </span>
                {!collapsed && item.comingSoon && (
                  <span
                    className="rounded border border-surface-border px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-surface-muted"
                    title="Planned for an upcoming phase"
                  >
                    Soon
                  </span>
                )}
                {!collapsed && item.showOpenCaseBadge && openCaseCount > 0 && (
                  <span
                    data-testid="open-case-badge"
                    className="rounded-full bg-[rgba(91,140,255,0.25)] px-2 py-0.5 text-[10px] font-semibold text-ink"
                    title={`${openCaseCount} open cases`}
                  >
                    {openCaseCount}
                  </span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {!collapsed && (
        <footer className="border-t border-surface-border px-5 py-3 text-[11px] text-surface-muted">
          v0.1.0 · Phase 2 inbox + cases
        </footer>
      )}
    </aside>
  );
}
