import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AlertsPage } from "../pages/AlertsPage";
import { LiveAlertFeed } from "../components/operations/LiveAlertFeed";
import * as alertsApi from "../api/alerts";
import { Alert } from "../types/api";

describe("Alert Triage & Workflow Tests", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockAlerts: Alert[] = [
    {
      alert_id: "alt_01",
      watchlist_id: "tgt_01",
      sighting_id: "sight_01",
      camera_id: "cam_sg_highway_01",
      stream_epoch: 1,
      track_id: 5,
      registration: "GJ01AB1234",
      match_score: 0.98,
      match_class: "EXACT",
      severity: "CRITICAL",
      created_at: new Date().toISOString(),
      acknowledged: false,
      explanation: ["Exact OCR consensus plate match confirmed"],
    },
    {
      alert_id: "alt_02",
      watchlist_id: "tgt_02",
      sighting_id: "sight_02",
      camera_id: "cam_ashram_rd_01",
      stream_epoch: 1,
      track_id: 8,
      registration: "GJ18XY5678",
      match_score: 0.92,
      match_class: "HIGH_PROBABILITY",
      severity: "HIGH",
      created_at: new Date().toISOString(),
      acknowledged: true,
      acknowledged_by: "Supervisor_01",
      acknowledged_at: new Date().toISOString(),
      explanation: ["High-probability match"],
    },
  ];

  it("renders live alert feed with match score and action buttons", () => {
    const handleAck = vi.fn();
    const handleInvestigate = vi.fn();

    render(
      <LiveAlertFeed
        alerts={mockAlerts}
        onAcknowledge={handleAck}
        onInvestigate={handleInvestigate}
      />
    );

    expect(screen.getByText("GJ01AB1234")).toBeDefined();
    expect(screen.getByText("cam_sg_highway_01")).toBeDefined();
    expect(screen.getByText("0.98")).toBeDefined();
    expect(screen.getByText("Acknowledge")).toBeDefined();
    expect(screen.getAllByText("Trace Trajectory").length).toBeGreaterThan(0);
  });

  it("acknowledges unacknowledged alert on click", () => {
    const handleAck = vi.fn();
    const handleInvestigate = vi.fn();

    render(
      <MemoryRouter>
        <AlertsPage
          alerts={mockAlerts}
          onAcknowledge={handleAck}
          onInvestigate={handleInvestigate}
        />
      </MemoryRouter>
    );

    const ackButtons = screen.getAllByRole("button", { name: /ack/i });
    fireEvent.click(ackButtons[0]);
    expect(handleAck).toHaveBeenCalledWith("alt_01");
  });

  it("filters alerts by unacknowledged only toggle", () => {
    render(
      <MemoryRouter>
        <AlertsPage
          alerts={mockAlerts}
          onAcknowledge={() => {}}
          onInvestigate={() => {}}
        />
      </MemoryRouter>
    );

    const checkbox = screen.getByLabelText("Unacknowledged Only");
    fireEvent.click(checkbox);

    expect(screen.getByText("GJ01AB1234")).toBeDefined();
    expect(screen.queryByText("GJ18XY5678")).toBeNull();
  });

  it("authoritatively fetches remote alert when deep-linked alertId is not in local cache", async () => {
    const remoteAlert: Alert = {
      alert_id: "alt_historical_99",
      watchlist_id: "tgt_99",
      sighting_id: "sight_99",
      camera_id: "cam_ring_rd_01",
      stream_epoch: 1,
      track_id: 19,
      registration: "GJ27ZZ9999",
      match_score: 0.97,
      match_class: "EXACT",
      severity: "CRITICAL",
      created_at: new Date().toISOString(),
      acknowledged: false,
      explanation: ["Exact OCR plate match confirmed"],
    };

    vi.spyOn(alertsApi, "getAlert").mockResolvedValue(remoteAlert);

    render(
      <MemoryRouter initialEntries={["/alerts/alt_historical_99"]}>
        <Routes>
          <Route
            path="/alerts/:alertId"
            element={
              <AlertsPage
                alerts={mockAlerts}
                onAcknowledge={() => {}}
                onInvestigate={() => {}}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(alertsApi.getAlert).toHaveBeenCalledWith("alt_historical_99");
      expect(screen.getByText("GJ27ZZ9999")).toBeDefined();
      expect(screen.getByText("cam_ring_rd_01")).toBeDefined();
    });
  });

  it("displays truthful not-found state when deep-linked alertId does not exist in backend", async () => {
    vi.spyOn(alertsApi, "getAlert").mockRejectedValue(new Error("Alert not found (404)"));

    render(
      <MemoryRouter initialEntries={["/alerts/nonexistent_alt_404"]}>
        <Routes>
          <Route
            path="/alerts/:alertId"
            element={
              <AlertsPage
                alerts={mockAlerts}
                onAcknowledge={() => {}}
                onInvestigate={() => {}}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Alert 'nonexistent_alt_404' not found in database.")).toBeDefined();
    });
  });
});
