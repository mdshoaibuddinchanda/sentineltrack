import { describe, it, expect } from "vitest";
import {
  formatDistance,
  formatSpeed,
  formatScore,
  formatDuration,
  formatDateTime,
  formatRelativeTime,
  maskRegistration,
} from "../utils/formatters";

describe("Frontend Formatters", () => {
  it("formats lower-bound distances correctly", () => {
    expect(formatDistance(450)).toBe("450 m");
    expect(formatDistance(12400)).toBe("12.4 km");
    expect(formatDistance(0)).toBe("0 m");
    expect(formatDistance(null)).toBe("--");
    expect(formatDistance(undefined)).toBe("--");
  });

  it("formats minimum required speed correctly", () => {
    expect(formatSpeed(65.4)).toBe("65 km/h");
    expect(formatSpeed(120)).toBe("120 km/h");
    expect(formatSpeed(null)).toBe("--");
  });

  it("formats match and trajectory scores to 2 decimal places", () => {
    expect(formatScore(0.9542)).toBe("0.95");
    expect(formatScore(1.0)).toBe("1.00");
    expect(formatScore(0)).toBe("0.00");
    expect(formatScore(null)).toBe("--");
  });

  it("formats duration in seconds to human readable strings", () => {
    expect(formatDuration(45)).toBe("45s");
    expect(formatDuration(150)).toBe("2m 30s");
    expect(formatDuration(3660)).toBe("1h 1m");
  });

  it("masks vehicle license registration strings for privacy mode", () => {
    expect(maskRegistration("GJ01AB1234", true)).toBe("GJ01****34");
    expect(maskRegistration("GJ01AB1234", false)).toBe("GJ01AB1234");
    expect(maskRegistration("DL1C", true)).toBe("DL1C");
  });

  it("formats relative time strings", () => {
    const now = new Date();
    const tenSecAgo = new Date(now.getTime() - 10000).toISOString();
    expect(formatRelativeTime(tenSecAgo)).toContain("10s ago");
  });
});
