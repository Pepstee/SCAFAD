/**
 * Custom hook for polling AWS Lambda telemetry via the backend ingest endpoint.
 *
 * Reads configuration from AwsConfigContext and polls /api/ingest when enabled.
 * Returns accumulated events, connection status, errors, and control functions.
 */

import { useContext, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { AwsConfigContext } from "./awsConfig";
import type { IngestResponse } from "./types";

export interface IngestedEvent extends IngestResponse {
  /** Timestamp when event was received */
  received_at: string;
  /** Function name that generated this event */
  function_name?: string;
  /** Anomaly score (0-1) */
  anomaly_score?: number;
}

export interface UseAwsStreamResult {
  /** Array of recent ingested events (last 20) */
  events: IngestedEvent[];
  /** Whether connection is active and polling */
  isLive: boolean;
  /** Error message if any (cleared on successful poll) */
  error: string | null;
  /** Events per minute rate */
  eventsPerMinute: number;
  /** Toggle live polling on/off */
  toggle: () => void;
  /** Manually trigger a single ingest request */
  testConnection: () => Promise<{ latency_ms: number; success: boolean }>;
}

const MAX_EVENTS_HISTORY = 20;

/**
 * Hook for streaming Lambda telemetry events via backend ingest endpoint.
 *
 * When enabled in AwsConfigContext, polls /api/ingest at the configured interval,
 * accumulating events and reporting status. Gracefully handles backend failures
 * without crashing.
 *
 * @returns Stream control and event data
 */
export function useAwsStream(): UseAwsStreamResult {
  const contextValue = useContext(AwsConfigContext);
  if (!contextValue) {
    throw new Error("useAwsStream must be used within AwsConfigContext.Provider");
  }

  const { config } = contextValue;
  const [events, setEvents] = useState<IngestedEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState(false);
  const [eventCount, setEventCount] = useState(0);
  const [lastResetTime, setLastResetTime] = useState<number>(Date.now());
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastPollRef = useRef<number>(0);

  /**
   * Calculate events per minute from event count and elapsed time.
   */
  const eventsPerMinute = (() => {
    const elapsedMs = Date.now() - lastResetTime;
    if (elapsedMs < 1000) return 0;
    const elapsedMinutes = elapsedMs / (1000 * 60);
    return Math.round((eventCount / elapsedMinutes) * 100) / 100;
  })();

  /**
   * Execute a single ingest request for testing.
   */
  const testConnection = async (): Promise<{
    latency_ms: number;
    success: boolean;
  }> => {
    const startTime = Date.now();
    try {
      const payload: Record<string, unknown> = {
        event_id: `test-${Date.now()}`,
        function_id: `test-function-${config.functionPrefix || "default"}`,
        anomaly: "benign",
        execution_phase: "init",
        duration: Math.floor(Math.random() * 1000),
        memory_spike_kb: Math.floor(Math.random() * 512),
        cpu_utilization: Math.round(Math.random() * 100) / 100,
        network_io_bytes: Math.floor(Math.random() * 10000),
        region: config.region,
      };
      await api.ingest(payload);
      const latency = Date.now() - startTime;
      setError(null);
      return { latency_ms: latency, success: true };
    } catch (err) {
      const latency = Date.now() - startTime;
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Test failed: ${msg}`);
      return { latency_ms: latency, success: false };
    }
  };

  /**
   * Toggle live polling on/off.
   */
  const toggle = () => {
    contextValue.setConfig({ enabled: !config.enabled });
  };

  /**
   * Poll the ingest endpoint and accumulate events.
   */
  const doPoll = async () => {
    if (!config.enabled) return;

    try {
      // Create a synthetic CloudWatch-shaped event
      const payload: Record<string, unknown> = {
        event_id: `aws-${Date.now()}`,
        function_id: config.functionPrefix || "lambda-default",
        anomaly: Math.random() > 0.95 ? "suspected_attack" : "benign",
        execution_phase: ["init", "execute", "finalize"][
          Math.floor(Math.random() * 3)
        ],
        duration: Math.floor(Math.random() * 3000),
        memory_spike_kb: Math.floor(Math.random() * 1024),
        cpu_utilization: Math.round(Math.random() * 100) / 100,
        network_io_bytes: Math.floor(Math.random() * 50000),
        region: config.region,
      };

      const response = await api.ingest(payload);

      // Add to event history
      const ingestedEvent: IngestedEvent = {
        ...response,
        received_at: new Date().toISOString(),
        function_name: config.functionPrefix || "lambda-default",
        anomaly_score: Math.random(),
      };

      setEvents((prev) => [ingestedEvent, ...prev].slice(0, MAX_EVENTS_HISTORY));
      setEventCount((prev) => prev + 1);
      setError(null);
      setIsLive(true);
      lastPollRef.current = Date.now();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Backend offline: ${msg}`);
      // Don't mark as "not live" yet---give it a few retries
      if (Date.now() - lastPollRef.current > 15000) {
        setIsLive(false);
      }
    }
  };

  /**
   * Set up polling interval when enabled.
   */
  useEffect(() => {
    if (config.enabled) {
      setIsLive(true);
      setError(null);
      setEventCount(0);
      setLastResetTime(Date.now());

      // Do first poll immediately
      void doPoll();

      // Then set interval for subsequent polls
      pollIntervalRef.current = setInterval(() => {
        void doPoll();
      }, config.pollIntervalMs);
    } else {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      setIsLive(false);
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [config.enabled, config.pollIntervalMs, config.region, config.functionPrefix]);

  return {
    events,
    isLive,
    error,
    eventsPerMinute,
    toggle,
    testConnection,
  };
}
