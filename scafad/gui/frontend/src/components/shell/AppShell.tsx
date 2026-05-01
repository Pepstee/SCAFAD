import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { useDetectionStream } from "@/lib/api";

export function AppShell() {
  // Subscribe to live detections.  Safely no-ops in jsdom test environments.
  useDetectionStream();
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface-base">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto px-6 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
