/**
 * Configured QueryClient for TanStack Query v5
 * Centralized configuration for all query caching and retry behavior.
 */

import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // 30 seconds
      gcTime: 5 * 60 * 1000, // 5 minutes (garbage collection)
      retry: 1,
      retryDelay: 1000,
    },
  },
});
