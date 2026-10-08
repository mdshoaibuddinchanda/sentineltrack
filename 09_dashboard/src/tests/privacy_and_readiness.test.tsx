import { describe, it, expect, vi } from "vitest";
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { TargetListTable } from "../components/targets/TargetListTable";
import { TrajectorySummaryCard } from "../components/investigation/TrajectorySummaryCard";
import { ReadinessMatrix } from "../components/system/ReadinessMatrix";
import { Header } from "../components/layout/Header";
import { Target, RouteResponse } from "../types/api";

describe("Privacy Mode & System Readiness Strict Truth Tests", () => {
  const mockTargets: Target[] = [
    {
      target_id: "tgt_01",
      registration: "GJ01AB1234",
      normalized_registration: "GJ01AB1234",
      priority: "CRITICAL",
      enabled: true,
      created_at: "2026-08-28T10:00:00Z",
      notes: "Robbery suspect",
    },
  ];

  it("privacy mode ON hides raw registration AND normalized registration in TargetListTable", () => {
    const { container } = render(
      <TargetListTable
        targets={mockTargets}
        onInvestigate={vi.fn()}
        privacyMode={true}
      />
    );

    // The raw registration 'GJ01AB1234' must NOT appear anywhere in the rendered HTML
    expect(container.textContent).not.toContain("GJ01AB1234");
    // Masked format 'GJ01****34' should appear
    expect(container.textContent).toContain("GJ01****34");
  });

  it("privacy mode ON hides raw registration in TrajectorySummaryCard", () => {
    const mockRoute: RouteResponse = {
      target_id: "tgt_01",
      registration: "GJ01AB1234",
      status: "PLAUSIBLE_SEQUENCE",
      trajectory_confidence: 0.95,
      total_lower_bound_distance_m: 5000,
      duration_seconds: 300,
      minimum_average_speed_kmh: 60,
      sighting_count: 3,
      camera_count: 3,
      alternative_trajectories_count: 0,
      sightings: [],
      segments: [],
      reasons: [],
      warnings: [],
      disclaimer: "Tactical trajectory representation",
    };

    const { container } = render(
      <TrajectorySummaryCard route={mockRoute} privacyMode={true} />
    );

    expect(container.textContent).not.toContain("GJ01AB1234");
    expect(container.textContent).toContain("GJ01****34");
  });

  it("absent/null readiness component is rendered as UNKNOWN, never falsely READY", () => {
    const mockPartialReadiness = {
      status: "DEGRADED",
      details: "Some components degraded",
      components: {
        database: true,
        postgis: false,
      },
    } as any;

    render(<ReadinessMatrix readiness={mockPartialReadiness} />);

    // Database is explicitly true -> READY
    expect(screen.getByText("READY")).toBeDefined();
    // PostGIS is explicitly false -> OFFLINE
    expect(screen.getByText("OFFLINE")).toBeDefined();
    // Omitted components (like route_engine, vehicle_detector, etc) must render UNKNOWN
    const unknownBadges = screen.getAllByText("UNKNOWN");
    expect(unknownBadges.length).toBeGreaterThan(0);
  });

  it("labels the privacy control clearly and invokes the toggle", () => {
    const onTogglePrivacyMode = vi.fn();

    render(
      <Header
        systemStatus="HEALTHY"
        wsStatus="LIVE"
        activeCamerasCount={30}
        activeTargetsCount={1}
        unackAlertsCount={0}
        liveFramesDecoded={100}
        darkMode={false}
        onToggleDarkMode={vi.fn()}
        onRefresh={vi.fn()}
        privacyMode={false}
        onTogglePrivacyMode={onTogglePrivacyMode}
      />
    );

    expect(screen.getByText("Privacy off")).toBeDefined();
    const privacyControl = screen.getByRole("button", {
      name: "Turn privacy mode on and hide registration numbers",
    });
    expect(privacyControl.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(privacyControl);
    expect(onTogglePrivacyMode).toHaveBeenCalledTimes(1);
  });
});
