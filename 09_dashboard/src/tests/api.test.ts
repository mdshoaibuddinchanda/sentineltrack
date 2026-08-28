import { describe, it, expect, vi, beforeEach } from "vitest";
import { searchNearbyCameras, getNearbyCamerasForCamera } from "../api/cameras";
import { listTargets } from "../api/targets";
import { listAlerts } from "../api/alerts";
import { getVehicleRoute, getVehicleRouteGeoJSON, getVehicleRouteSummary } from "../api/routes";

describe("P8 REST API Contract Verification", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("nearby cameras sends 'lat' and 'lon' and handles raw Camera array", async () => {
    const mockCameras = [
      {
        camera_id: "cam_01",
        stream_status: "ONLINE",
        location_quality: "VERIFIED",
        live: true,
      },
    ];

    let capturedUrl = "";
    global.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = url.toString();
      return Promise.resolve({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockCameras,
      } as any);
    });

    const res = await searchNearbyCameras(23.0298, 72.5067, 5000);
    expect(capturedUrl).toContain("lat=23.0298");
    expect(capturedUrl).toContain("lon=72.5067");
    expect(capturedUrl).toContain("radius_m=5000");
    expect(capturedUrl).not.toContain("latitude=");
    expect(capturedUrl).not.toContain("longitude=");
    expect(Array.isArray(res)).toBe(true);
    expect(res[0].camera_id).toBe("cam_01");
  });

  it("listTargets sends 'enabled' parameter, NOT 'enabled_only'", async () => {
    let capturedUrl = "";
    global.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = url.toString();
      return Promise.resolve({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ items: [], total: 0 }),
      } as any);
    });

    await listTargets({ enabled: true, priority: "CRITICAL" });
    expect(capturedUrl).toContain("enabled=true");
    expect(capturedUrl).toContain("priority=CRITICAL");
    expect(capturedUrl).not.toContain("enabled_only");
  });

  it("listAlerts sends 'unacknowledged' parameter, NOT 'unacknowledged_only'", async () => {
    let capturedUrl = "";
    global.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = url.toString();
      return Promise.resolve({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ items: [], total: 0, unacknowledged_count: 0 }),
      } as any);
    });

    await listAlerts({ unacknowledged: true });
    expect(capturedUrl).toContain("unacknowledged=true");
    expect(capturedUrl).not.toContain("unacknowledged_only");
  });

  it("route engine requests send 'min_match_score', NOT 'min_confidence'", async () => {
    let capturedUrl = "";
    global.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = url.toString();
      return Promise.resolve({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ registration: "GJ01AB1234", status: "PLAUSIBLE_SEQUENCE" }),
      } as any);
    });

    await getVehicleRoute("GJ01AB1234", { min_match_score: 0.75 });
    expect(capturedUrl).toContain("min_match_score=0.75");
    expect(capturedUrl).not.toContain("min_confidence");

    await getVehicleRouteGeoJSON("GJ01AB1234", { min_match_score: 0.8 });
    expect(capturedUrl).toContain("min_match_score=0.8");

    await getVehicleRouteSummary("GJ01AB1234", { min_match_score: 0.85 });
    expect(capturedUrl).toContain("min_match_score=0.85");
  });
});
