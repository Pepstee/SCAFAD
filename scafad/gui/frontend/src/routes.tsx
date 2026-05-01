import { lazy, Suspense } from "react";
import { Navigate, RouteObject } from "react-router-dom";

import { AppShell } from "@/components/shell/AppShell";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";

const Dashboard = lazy(() => import("@/pages/Dashboard"));
const DetectionDetail = lazy(() => import("@/pages/DetectionDetail"));
const Inbox = lazy(() => import("@/pages/Inbox"));
const Cases = lazy(() => import("@/pages/Cases"));
const Functions = lazy(() => import("@/pages/Functions"));
const ThreatMap = lazy(() => import("@/pages/ThreatMap"));
const SystemStatus = lazy(() => import("@/pages/SystemStatus"));
const Settings = lazy(() => import("@/pages/Settings"));
const Audit = lazy(() => import("@/pages/Audit"));

function withSuspense(node: JSX.Element): JSX.Element {
  return <Suspense fallback={<LoadingSpinner />}>{node}</Suspense>;
}

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: withSuspense(<Dashboard />) },
      { path: "detections/:id", element: withSuspense(<DetectionDetail />) },
      { path: "inbox", element: withSuspense(<Inbox />) },
      { path: "cases", element: withSuspense(<Cases />) },
      { path: "functions", element: withSuspense(<Functions />) },
      { path: "threat-map", element: withSuspense(<ThreatMap />) },
      { path: "system", element: withSuspense(<SystemStatus />) },
      { path: "settings", element: withSuspense(<Settings />) },
      { path: "audit", element: withSuspense(<Audit />) },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
];
