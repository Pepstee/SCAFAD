import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReactNode } from "react";
import React from "react";

import {
  AwsConfigContext,
  getDefaultConfig,
  type AwsConfigContextValue,
} from "@/lib/awsConfig";
import type { AwsConfig } from "@/lib/awsConfig";

describe("AWS Integration - Context Functionality", () => {
  it("AwsConfigContext.Provider makes config accessible to children", () => {
    const testConfig: AwsConfig = {
      region: "us-east-1",
      functionPrefix: "test-",
      pollIntervalMs: 5000,
      enabled: false,
    };

    const contextValue: AwsConfigContextValue = {
      config: testConfig,
      setConfig: () => {},
      reset: () => {},
    };

    let capturedConfig: AwsConfig | null = null;

    const TestChild = () => {
      const context = React.useContext(AwsConfigContext);
      if (context) {
        capturedConfig = context.config;
      }
      return <div>{context?.config.region}</div>;
    };

    render(
      <AwsConfigContext.Provider value={contextValue}>
        <TestChild />
      </AwsConfigContext.Provider>
    );

    expect(capturedConfig).toEqual(testConfig);
    expect(screen.getByText("us-east-1")).toBeInTheDocument();
  });

  it("context provides all required properties", () => {
    const testConfig = getDefaultConfig();
    const contextValue: AwsConfigContextValue = {
      config: testConfig,
      setConfig: () => {},
      reset: () => {},
    };

    const TestComponent = () => {
      const context = React.useContext(AwsConfigContext);
      if (!context) return <div>No context</div>;

      return (
        <div>
          <div data-testid="has-config">{context.config ? "yes" : "no"}</div>
          <div data-testid="has-setconfig">
            {typeof context.setConfig === "function" ? "yes" : "no"}
          </div>
          <div data-testid="has-reset">
            {typeof context.reset === "function" ? "yes" : "no"}
          </div>
        </div>
      );
    };

    render(
      <AwsConfigContext.Provider value={contextValue}>
        <TestComponent />
      </AwsConfigContext.Provider>
    );

    expect(screen.getByTestId("has-config")).toHaveTextContent("yes");
    expect(screen.getByTestId("has-setconfig")).toHaveTextContent("yes");
    expect(screen.getByTestId("has-reset")).toHaveTextContent("yes");
  });

  it("multiple children can access the same context", () => {
    const contextValue: AwsConfigContextValue = {
      config: getDefaultConfig(),
      setConfig: () => {},
      reset: () => {},
    };

    const Child1 = () => {
      const context = React.useContext(AwsConfigContext);
      return <div>{context?.config.region}</div>;
    };

    const Child2 = () => {
      const context = React.useContext(AwsConfigContext);
      return <div>{context?.config.functionPrefix || "no-prefix"}</div>;
    };

    render(
      <AwsConfigContext.Provider value={contextValue}>
        <Child1 />
        <Child2 />
      </AwsConfigContext.Provider>
    );

    expect(screen.getByText("eu-west-1")).toBeInTheDocument();
    expect(screen.getByText("no-prefix")).toBeInTheDocument();
  });

  it("context value can be updated by providing new value", () => {
    const config1: AwsConfig = {
      region: "eu-west-1",
      functionPrefix: "",
      pollIntervalMs: 5000,
      enabled: false,
    };

    const contextValue1: AwsConfigContextValue = {
      config: config1,
      setConfig: () => {},
      reset: () => {},
    };

    const TestComponent = ({ value }: { value: AwsConfigContextValue }) => {
      const context = React.useContext(AwsConfigContext);
      return <div data-testid="region">{context?.config.region}</div>;
    };

    const { rerender } = render(
      <AwsConfigContext.Provider value={contextValue1}>
        <TestComponent value={contextValue1} />
      </AwsConfigContext.Provider>
    );

    expect(screen.getByTestId("region")).toHaveTextContent("eu-west-1");

    // Update context with new value
    const config2: AwsConfig = {
      region: "ap-southeast-1",
      functionPrefix: "",
      pollIntervalMs: 5000,
      enabled: false,
    };

    const contextValue2: AwsConfigContextValue = {
      config: config2,
      setConfig: () => {},
      reset: () => {},
    };

    rerender(
      <AwsConfigContext.Provider value={contextValue2}>
        <TestComponent value={contextValue2} />
      </AwsConfigContext.Provider>
    );

    expect(screen.getByTestId("region")).toHaveTextContent("ap-southeast-1");
  });

  it("context is null when not provided (optional)", () => {
    const TestComponent = () => {
      const context = React.useContext(AwsConfigContext);
      return <div>{context ? "provided" : "not-provided"}</div>;
    };

    render(<TestComponent />);

    expect(screen.getByText("not-provided")).toBeInTheDocument();
  });
});

describe("AWS Config - Type Safety", () => {
  it("AwsConfig interface enforces required fields at compile time", () => {
    const validConfig: AwsConfig = {
      region: "eu-west-1",
      functionPrefix: "",
      pollIntervalMs: 5000,
      enabled: false,
    };

    expect(validConfig.region).toBe("eu-west-1");
    expect(validConfig.functionPrefix).toBe("");
    expect(validConfig.pollIntervalMs).toBe(5000);
    expect(validConfig.enabled).toBe(false);
  });

  it("AwsConfigContextValue includes required methods", () => {
    const contextValue: AwsConfigContextValue = {
      config: getDefaultConfig(),
      setConfig: () => {},
      reset: () => {},
    };

    expect(typeof contextValue.setConfig).toBe("function");
    expect(typeof contextValue.reset).toBe("function");
  });

  it("getDefaultConfig returns fresh instance with correct structure", () => {
    const config1 = getDefaultConfig();
    const config2 = getDefaultConfig();

    expect(config1).not.toBe(config2); // Different objects
    expect(config1).toEqual(config2); // Same values
    expect(config1.region).toBe("eu-west-1");
    expect(config1.enabled).toBe(false);
  });
});

describe("AWS Config - Context Provider Integration", () => {
  it("nested contexts work correctly", () => {
    const outerConfig = getDefaultConfig();
    outerConfig.region = "us-east-1";

    const innerConfig = getDefaultConfig();
    innerConfig.region = "ap-northeast-1";

    const OuterContext: AwsConfigContextValue = {
      config: outerConfig,
      setConfig: () => {},
      reset: () => {},
    };

    const InnerContext: AwsConfigContextValue = {
      config: innerConfig,
      setConfig: () => {},
      reset: () => {},
    };

    const Inner = () => {
      const context = React.useContext(AwsConfigContext);
      return <div data-testid="inner">{context?.config.region}</div>;
    };

    const Outer = () => {
      const context = React.useContext(AwsConfigContext);
      return (
        <div>
          <div data-testid="outer">{context?.config.region}</div>
          <AwsConfigContext.Provider value={InnerContext}>
            <Inner />
          </AwsConfigContext.Provider>
        </div>
      );
    };

    render(
      <AwsConfigContext.Provider value={OuterContext}>
        <Outer />
      </AwsConfigContext.Provider>
    );

    expect(screen.getByTestId("outer")).toHaveTextContent("us-east-1");
    expect(screen.getByTestId("inner")).toHaveTextContent("ap-northeast-1");
  });
});
