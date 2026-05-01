import { describe, expect, it } from "vitest";
import {
  validatePollInterval,
  getDefaultConfig,
  AwsConfig,
} from "@/lib/awsConfig";

describe("awsConfig helpers", () => {
  describe("validatePollInterval", () => {
    it("clamps values below minimum to 1000ms", () => {
      expect(validatePollInterval(500)).toBe(1000);
      expect(validatePollInterval(0)).toBe(1000);
      expect(validatePollInterval(-1000)).toBe(1000);
    });

    it("clamps values above maximum to 30000ms", () => {
      expect(validatePollInterval(40000)).toBe(30000);
      expect(validatePollInterval(50000)).toBe(30000);
      expect(validatePollInterval(100000)).toBe(30000);
    });

    it("allows values within valid range (1000-30000)", () => {
      expect(validatePollInterval(1000)).toBe(1000);
      expect(validatePollInterval(5000)).toBe(5000);
      expect(validatePollInterval(15000)).toBe(15000);
      expect(validatePollInterval(30000)).toBe(30000);
    });

    it("handles edge cases at boundaries", () => {
      expect(validatePollInterval(999)).toBe(1000);
      expect(validatePollInterval(1001)).toBe(1001);
      expect(validatePollInterval(29999)).toBe(29999);
      expect(validatePollInterval(30001)).toBe(30000);
    });
  });

  describe("getDefaultConfig", () => {
    it("returns a default AwsConfig object", () => {
      const config = getDefaultConfig();
      expect(config).toBeDefined();
      expect(typeof config).toBe("object");
    });

    it("sets region to eu-west-1", () => {
      const config = getDefaultConfig();
      expect(config.region).toBe("eu-west-1");
    });

    it("sets functionPrefix to empty string", () => {
      const config = getDefaultConfig();
      expect(config.functionPrefix).toBe("");
    });

    it("sets pollIntervalMs to 5000", () => {
      const config = getDefaultConfig();
      expect(config.pollIntervalMs).toBe(5000);
    });

    it("sets enabled to false", () => {
      const config = getDefaultConfig();
      expect(config.enabled).toBe(false);
    });

    it("returns a new object each call (not a singleton)", () => {
      const config1 = getDefaultConfig();
      const config2 = getDefaultConfig();
      expect(config1).not.toBe(config2);
      expect(config1).toEqual(config2);
    });

    it("modifying returned config does not affect subsequent calls", () => {
      const config1 = getDefaultConfig();
      config1.region = "us-east-1";
      config1.enabled = true;

      const config2 = getDefaultConfig();
      expect(config2.region).toBe("eu-west-1");
      expect(config2.enabled).toBe(false);
    });
  });

  describe("AwsConfig interface", () => {
    it("has required properties", () => {
      const config: AwsConfig = {
        region: "eu-west-1",
        functionPrefix: "prod-",
        pollIntervalMs: 5000,
        enabled: true,
      };

      expect(config.region).toBe("eu-west-1");
      expect(config.functionPrefix).toBe("prod-");
      expect(config.pollIntervalMs).toBe(5000);
      expect(config.enabled).toBe(true);
    });
  });
});
