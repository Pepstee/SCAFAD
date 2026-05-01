import { useMemo, useState, useCallback } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { routes } from "./routes";
import { queryClient } from "./lib/queryClient";
import { AwsConfigContext_Provider, getDefaultConfig } from "./lib/awsConfig";
import type { AwsConfig, AwsConfigContextValue } from "./lib/awsConfig";

export function App() {
  const router = useMemo(() => createBrowserRouter(routes), []);

  // AWS Config state management
  const [awsConfig, setAwsConfig] = useState<AwsConfig>(getDefaultConfig());

  const handleSetConfig = useCallback((partialConfig: Partial<AwsConfig>) => {
    setAwsConfig((prev) => ({ ...prev, ...partialConfig }));
  }, []);

  const handleReset = useCallback(() => {
    setAwsConfig(getDefaultConfig());
  }, []);

  const awsConfigValue: AwsConfigContextValue = {
    config: awsConfig,
    setConfig: handleSetConfig,
    reset: handleReset,
  };

  return (
    <QueryClientProvider client={queryClient}>
      <AwsConfigContext_Provider value={awsConfigValue}>
        <RouterProvider router={router} />
      </AwsConfigContext_Provider>
    </QueryClientProvider>
  );
}

export default App;
