/**
 * AWS configuration context and types for live Lambda telemetry polling.
 *
 * Provides centralized configuration state for region, function prefix,
 * polling interval, and enable/disable toggle, accessible to all components
 * via React Context.
 */

import { createContext, ReactNode } from "react";

/**
 * Configuration for AWS Lambda telemetry streaming.
 */
export interface AwsConfig {
  /** AWS region (e.g., 'eu-west-1') */
  region: string;
  /** Function name prefix filter */
  functionPrefix: string;
  /** Polling interval in milliseconds (1000-30000 ms) */
  pollIntervalMs: number;
  /** Whether live polling is enabled */
  enabled: boolean;
}

/**
 * Context value: current config + setter function.
 */
export interface AwsConfigContextValue {
  config: AwsConfig;
  setConfig: (config: Partial<AwsConfig>) => void;
  reset: () => void;
}

/**
 * Default AWS configuration.
 */
const DEFAULT_CONFIG: AwsConfig = {
  region: "eu-west-1",
  functionPrefix: "",
  pollIntervalMs: 5000,
  enabled: false,
};

/**
 * React Context for AWS configuration.
 * Provides read/write access to polling settings across the app.
 */
export const AwsConfigContext = createContext<AwsConfigContextValue | null>(
  null
);

export const AwsConfigContext_Provider = AwsConfigContext.Provider;

/**
 * Helper to validate and clamp poll interval to safe bounds.
 */
export function validatePollInterval(ms: number): number {
  const MIN_MS = 1000;  // Minimum 1 second
  const MAX_MS = 30000; // Maximum 30 seconds
  return Math.max(MIN_MS, Math.min(MAX_MS, ms));
}

/**
 * Get default config for fresh initialization.
 */
export function getDefaultConfig(): AwsConfig {
  return { ...DEFAULT_CONFIG };
}
