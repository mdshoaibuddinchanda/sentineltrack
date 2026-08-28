import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAlerts } from "../hooks/useAlerts";
import { Alert } from "../types/api";

describe("Alerts Idempotency & Evidence Integrity Tests", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("prependLiveAlert is strictly idempotent for alert list, total, and unackCount", () => {
    const { result } = renderHook(() => useAlerts(undefined, true));

    const initialTotal = result.current.total;
    const initialUnack = result.current.unackCount;

    const liveAlert: Alert = {
      alert_id: "alt_unique_99",
      watchlist_id: "tgt_01",
      sighting_id: "sight_01",
      camera_id: "cam_sg_highway_01",
      stream_epoch: 1,
      track_id: 42,
      registration: "GJ01AB9999",
      match_score: 0.96,
      match_class: "EXACT",
      severity: "CRITICAL",
      created_at: new Date().toISOString(),
      acknowledged: false,
      explanation: ["Exact OCR plate match confirmed"],
    };

    // First insertion
    act(() => {
      result.current.prependLiveAlert(liveAlert);
    });

    expect(result.current.alerts[0].alert_id).toBe("alt_unique_99");
    expect(result.current.total).toBe(initialTotal + 1);
    expect(result.current.unackCount).toBe(initialUnack + 1);

    // Second duplicate insertion with same alert_id
    act(() => {
      result.current.prependLiveAlert(liveAlert);
    });

    // Counts and list length must remain identical (no duplicate increment)
    expect(result.current.alerts.filter((a) => a.alert_id === "alt_unique_99").length).toBe(1);
    expect(result.current.total).toBe(initialTotal + 1);
    expect(result.current.unackCount).toBe(initialUnack + 1);
  });

  it("acknowledged live alert does not increment unackCount", () => {
    const { result } = renderHook(() => useAlerts(undefined, true));

    const initialTotal = result.current.total;
    const initialUnack = result.current.unackCount;

    const ackedAlert: Alert = {
      alert_id: "alt_acked_01",
      watchlist_id: "tgt_02",
      sighting_id: "sight_02",
      camera_id: "cam_vastrapur_01",
      stream_epoch: 1,
      track_id: 12,
      registration: "GJ01AB1111",
      match_score: 0.91,
      match_class: "HIGH_PROBABILITY",
      severity: "HIGH",
      created_at: new Date().toISOString(),
      acknowledged: true,
      acknowledged_by: "Supervisor_01",
      explanation: ["High-probability match"],
    };

    act(() => {
      result.current.prependLiveAlert(ackedAlert);
    });

    expect(result.current.total).toBe(initialTotal + 1);
    expect(result.current.unackCount).toBe(initialUnack); // Not incremented
  });
});
