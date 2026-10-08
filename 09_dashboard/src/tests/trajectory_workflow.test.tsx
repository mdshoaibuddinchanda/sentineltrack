import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
import { TrajectorySummaryCard } from "../components/investigation/TrajectorySummaryCard";
import { SightingTimeline } from "../components/investigation/SightingTimeline";
import { KinematicSegmentsTable } from "../components/investigation/KinematicSegmentsTable";
import { WarningsPanel } from "../components/investigation/WarningsPanel";
import { TEST_ROUTE } from "./testFixtures";

describe("Trajectory Kinematics & Investigation Tests", () => {
  it("renders trajectory summary card with metrics", () => {
    render(<TrajectorySummaryCard route={TEST_ROUTE} />);

    expect(screen.getByText("GJ01AB1234")).toBeDefined();
    expect(screen.getByText("PLAUSIBLE TRAJECTORY")).toBeDefined();
    expect(screen.getByText("0.94")).toBeDefined(); // confidence
    expect(screen.getByText("8.4 km")).toBeDefined(); // lower bound distance
    expect(screen.getByText("37 km/h")).toBeDefined(); // min avg speed
  });

  it("renders chronological sighting timeline with camera IDs and time quality", () => {
    const handleSelect = vi.fn();
    render(
      <SightingTimeline
        sightings={TEST_ROUTE.sightings}
        onSelectSighting={handleSelect}
      />
    );

    expect(screen.getByText("cam_vastrapur_01")).toBeDefined();
    expect(screen.getByText("cam_ashram_rd_01")).toBeDefined();
    expect(screen.getByText("cam_sg_highway_01")).toBeDefined();
    expect(screen.getByText("cam_sg_highway_02")).toBeDefined();
  });

  it("renders kinematic segment table with lower-bound distances and required speeds", () => {
    render(<KinematicSegmentsTable segments={TEST_ROUTE.segments} />);

    expect(screen.getByText("4.3 km")).toBeDefined();
    expect(screen.getByText("71 km/h")).toBeDefined();
    expect(screen.getAllByText("FEASIBLE").length).toBeGreaterThan(0);
    expect(screen.getByText("121 km/h")).toBeDefined();
    expect(screen.getByText("QUESTIONABLE")).toBeDefined();
  });

  it("renders conflict and ambiguity warning panels when present", () => {
    const { rerender } = render(
      <WarningsPanel
        status="CONFLICTING_SIGHTINGS"
        warnings={["Physical speed violation detected (>200 km/h)"]}
      />
    );

    expect(screen.getByText("PHYSICAL TRAJECTORY CONFLICT DETECTED")).toBeDefined();
    expect(screen.getByText("Physical speed violation detected (>200 km/h)")).toBeDefined();

    rerender(
      <WarningsPanel
        status="AMBIGUOUS"
        reasons={["Multiple branching paths observed"]}
      />
    );

    expect(screen.getByText("AMBIGUOUS TRAJECTORY CANDIDATES")).toBeDefined();
    expect(screen.getByText("Multiple branching paths observed")).toBeDefined();
  });
});
