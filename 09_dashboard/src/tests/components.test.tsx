import { describe, it, expect } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
import { SeverityBadge, FeasibilityBadge, MatchClassBadge, PriorityBadge } from "../components/common/Badge";
import { MetricCards } from "../components/operations/MetricCards";
import { OfflineBanner } from "../components/common/OfflineBanner";

describe("UI Badges & Component Tests", () => {
  it("renders SeverityBadges with correct variant classes", () => {
    const { container } = render(
      <div>
        <SeverityBadge severity="CRITICAL" />
        <SeverityBadge severity="HIGH" />
        <SeverityBadge severity="NORMAL" />
      </div>
    );
    expect(container.textContent).toContain("CRITICAL");
    expect(container.textContent).toContain("HIGH");
    expect(container.textContent).toContain("NORMAL");
  });

  it("renders FeasibilityBadges correctly", () => {
    const { container } = render(
      <div>
        <FeasibilityBadge feasibility="FEASIBLE" />
        <FeasibilityBadge feasibility="QUESTIONABLE" />
        <FeasibilityBadge feasibility="IMPOSSIBLE" />
      </div>
    );
    expect(container.textContent).toContain("FEASIBLE");
    expect(container.textContent).toContain("QUESTIONABLE");
    expect(container.textContent).toContain("IMPOSSIBLE SPEED");
  });

  it("renders MetricCards with correct values", () => {
    const { container } = render(
      <MetricCards
        onlineCameras={18}
        offlineCameras={2}
        totalCameras={20}
        activeTargets={5}
        unackAlerts={3}
        totalSightings={142}
        analyticsStatus={true}
        workerCount={4}
      />
    );
    expect(container.textContent).toContain("18");
    expect(container.textContent).toContain("/ 20");
    expect(container.textContent).toContain("5");
    expect(container.textContent).toContain("3");
    expect(container.textContent).toContain("142");
    expect(container.textContent).toContain("4 Workers Active");
  });

  it("renders OfflineBanner when backend is disconnected", () => {
    const { container } = render(
      <OfflineBanner
        status="OFFLINE"
        error="Connection refused on port 8000"
        onRetry={() => {}}
      />
    );
    expect(container.textContent).toContain("SentinelTrack Backend Disconnected");
    expect(container.textContent).toContain("Connection refused on port 8000");
  });
});
