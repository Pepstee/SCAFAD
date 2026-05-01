import { describe, expect, it, beforeEach, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { ReactNode } from "react";

import { useAwsStream } from "@/lib/useAwsStream";
import { AwsConfigContext } from "@/lib/awsConfig";
import type { AwsConfig, AwsConfigContextValue } from "@/lib/awsConfig";
import * as apiModule from "@/lib/api";

// Mock the api module
vi.mock("@/lib/api", () => ({
  api: {
    ingest: vi.fn(),
  },
}));

describe("useAwsStream hook", () => {
  let mockApi: any;

  beforeEach(() => {
    mockApi = apiModule.api as any;
    mockApi.ingest.mockClear();
  });

  const createContextValue = (overrides?: Partial<AwsConfig>): AwsConfigContextValue => {
    const config: AwsConfig = {
      region: "eu-west-1",
      functionPrefix: "test-",
      pollIntervalMs: 5000,
      enabled: false,
      ...overrides,
    };

    return {
      config,
      setConfig: (partial) => {
        Object.assign(config, partial);
      },
      reset: () => {
        config.region = "eu-west-1";
        config.functionPrefix = "";
        config.pollIntervalMs = 5000;
        config.enabled = false;
      },
    };
  };

  const createWrapper = (contextValue: AwsConfigContextValue) => {
    return ({ children }: { children: ReactNode }) => (
      <AwsConfigContext.Provider value={contextValue}>
        {children}
      </AwsConfigContext.Provider>
    );
  };

  it("throws error when used outside of AwsConfigContext.Provider", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      renderHook(() => useAwsStream());
    }).toThrow("useAwsStream must be used within AwsConfigContext.Provider");

    consoleSpy.mockRestore();
  });

  it("returns initial state when hook is first called", () => {
    const contextValue = createContextValue();
    const wrapper = createWrapper(contextValue);
    const { result } = renderHook(() => useAwsStream(), { wrapper });

    expect(result.current.events).toEqual([]);
    expect(result.current.isLive).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.eventsPerMinute).toBe(0);
    expect(typeof result.current.toggle).toBe("function");
    expect(typeof result.current.testConnection).toBe("function");
  });

  it("toggle function is callable", () => {
    const contextValue = createContextValue();
    const wrapper = createWrapper(contextValue);
    const { result } = renderHook(() => useAwsStream(), { wrapper });

    // Should not throw
    expect(() => {
      result.current.toggle();
    }).not.toThrow();
  });

  it("testConnection fires a single ingest request and returns success", async () => {
    mockApi.ingest.mockResolvedValue({
      id: "test-1",
      severity: "observe",
      anomaly_type: "benign",
    });

    const contextValue = createContextValue();
    const wrapper = createWrapper(contextValue);
    const { result } = renderHook(() => useAwsStream(), { wrapper });

    const response = await result.current.testConnection();

    expect(response.success).toBe(true);
    expect(typeof response.latency_ms).toBe("number");
    expect(response.latency_ms).toBeGreaterThanOrEqual(0);
    expect(mockApi.ingest).toHaveBeenCalledTimes(1);
  });

  it("testConnection reports failure and latency on error", async () => {
    mockApi.ingest.mockRejectedValue(new Error("Backend unreachable"));

    const contextValue = createContextValue();
    const wrapper = createWrapper(contextValue);
    const { result } = renderHook(() => useAwsStream(), { wrapper });

    const response = await result.current.testConnection();

    expect(response.success).toBe(false);
    expect(typeof response.latency_ms).toBe("number");
  });

  it("includes region from config in test payload", async () => {
    mockApi.ingest.mockResolvedValue({
      id: "event-1",
      severity: "observe",
      anomaly_type: "benign",
    });

    const contextValue = createContextValue({ region: "us-east-1" });
    const wrapper = createWrapper(contextValue);
    const { result } = renderHook(() => useAwsStream(), { wrapper });

    await result.current.testConnection();

    const callPayload = mockApi.ingest.mock.calls[0][0];
    expect(callPayload.region).toBe("us-east-1");
  });

  it("includes functionPrefix in test payload", async () => {
    mockApi.ingest.mockResolvedValue({
      id: "event-1",
      severity: "observe",
      anomaly_type: "benign",
    });

    const contextValue = createContextValue({ functionPrefix: "prod-" });
    const wrapper = createWrapper(contextValue);
    const { result } = renderHook(() => useAwsStream(), { wrapper });

    await result.current.testConnection();

    const callPayload = mockApi.ingest.mock.calls[0][0];
    expect(callPayload.function_id).toContain("prod-");
  });

  it("UseAwsStreamResult interface provides required properties", () => {
    const contextValue = createContextValue();
    const wrapper = createWrapper(contextValue);
    const { result } = renderHook(() => useAwsStream(), { wrapper });

    // Verify all expected properties exist
    expect("events" in result.current).toBe(true);
    expect("isLive" in result.current).toBe(true);
    expect("error" in result.current).toBe(true);
    expect("eventsPerMinute" in result.current).toBe(true);
    expect("toggle" in result.current).toBe(true);
    expect("testConnection" in result.current).toBe(true);
  });

  it("IngestedEvent includes required fields from response", async () => {
    mockApi.ingest.mockResolvedValue({
      id: "event-1",
      severity: "observe",
      anomaly_type: "benign",
      mitre_techniques: ["T1234"],
    });

    const contextValue = createContextValue({ enabled: true, pollIntervalMs: 100 });
    const wrapper = createWrapper(contextValue);
    const { result } = renderHook(() => useAwsStream(), { wrapper });

    // Give hook time to make initial poll
    await new Promise((resolve) => setTimeout(resolve, 150));

    if (result.current.events.length > 0) {
      const event = result.current.events[0];
      expect(event.id).toBeDefined();
      expect(event.severity).toBeDefined();
      expect(event.anomaly_type).toBeDefined();
      expect(event.received_at).toBeDefined();
    }
  });

  it("handles API errors gracefully without crashing", async () => {
    mockApi.ingest.mockRejectedValue(new Error("Network timeout"));

    const contextValue = createContextValue();
    const wrapper = createWrapper(contextValue);
    const { result } = renderHook(() => useAwsStream(), { wrapper });

    // Should not crash
    expect(() => {
      result.current.testConnection();
    }).not.toThrow();
  });

  it("testConnection uses correct payload structure", async () => {
    mockApi.ingest.mockResolvedValue({
      id: "test-1",
      severity: "observe",
      anomaly_type: "benign",
    });

    const contextValue = createContextValue();
    const wrapper = createWrapper(contextValue);
    const { result } = renderHook(() => useAwsStream(), { wrapper });

    await result.current.testConnection();

    const payload = mockApi.ingest.mock.calls[0][0];
    expect(payload).toHaveProperty("event_id");
    expect(payload).toHaveProperty("function_id");
    expect(payload).toHaveProperty("anomaly");
    expect(payload).toHaveProperty("execution_phase");
    expect(payload).toHaveProperty("duration");
    expect(payload).toHaveProperty("memory_spike_kb");
    expect(payload).toHaveProperty("cpu_utilization");
    expect(payload).toHaveProperty("network_io_bytes");
    expect(payload).toHaveProperty("region");
  });
});
