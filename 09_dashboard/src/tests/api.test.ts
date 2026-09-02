import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  bulkImportCameras,
  createCamera,
  getCameraGapAnalysis,
  getNearbyCamerasForCamera,
  fetchCameraPreview,
  getCameraLiveStreamUrl,
  listVMSConnectors,
  searchNearbyCameras,
} from "../api/cameras";
import { listTargets } from "../api/targets";
import { listAlerts } from "../api/alerts";
import { checkCameraPairFeasibility, getVehicleRoute, getVehicleRouteGeoJSON, getVehicleRouteSummary } from "../api/routes";

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

  it("camera-specific nearby lookup encodes the camera ID and radius", async () => {
    let capturedUrl = "";
    global.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = url.toString();
      return Promise.resolve({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => [],
      } as any);
    });

    const res = await getNearbyCamerasForCamera("cam/01", 2500);
    expect(capturedUrl).toContain("/api/v1/cameras/cam%2F01/nearby");
    expect(capturedUrl).toContain("radius_m=2500");
    expect(res).toEqual([]);
  });

  it("loads camera previews with authenticated fetch credentials", async () => {
    let capturedInit: RequestInit | undefined;
    const preview = new Blob(["jpeg"], { type: "image/jpeg" });
    global.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedInit = init;
      return Promise.resolve({ ok: true, blob: async () => preview } as any);
    });

    const result = await fetchCameraPreview("cam/01");
    expect(capturedInit?.credentials).toBe("include");
    expect(capturedInit?.cache).toBe("no-store");
    expect(result).toBe(preview);
  });

  it("builds an authenticated live stream endpoint without exposing upstream URLs", () => {
    const url = getCameraLiveStreamUrl("cam/01", 12345);
    expect(url).toContain("/api/v1/cameras/cam%2F01/live");
    expect(url).toContain("session=12345");
    expect(url).not.toContain("rtsp");
    expect(url).not.toContain("m3u8");
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

  it("uses the audited camera registry contracts for manual and bulk onboarding", async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = [];
    global.fetch = vi.fn().mockImplementation((url, init) => {
      requests.push({ url: url.toString(), init });
      return Promise.resolve({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => init?.method === "POST" && url.toString().endsWith("/bulk")
          ? { dry_run: true, received: 1, valid: 1, created: 1, updated: 0, skipped: 0, items: [] }
          : { camera: { camera_id: "cam-01" }, created: true, worker_status: "STARTED" },
      } as any);
    });

    await createCamera({ camera_id: "cam-01", source_system: "MANUAL", location_quality: "UNKNOWN" });
    await bulkImportCameras(
      [{ camera_id: "cam-02", source_system: "CSV_IMPORT", location_quality: "UNKNOWN" }],
      { mode: "CREATE_ONLY", dry_run: true },
    );

    expect(requests[0].url).toContain("/api/v1/cameras");
    expect(requests[0].init?.method).toBe("POST");
    expect(JSON.parse(String(requests[0].init?.body))).toMatchObject({ camera_id: "cam-01" });
    expect(JSON.parse(String(requests[1].init?.body))).toMatchObject({ mode: "CREATE_ONLY", dry_run: true });
  });

  it("exposes gap evidence, connector readiness, and pair feasibility through explicit endpoints", async () => {
    const urls: string[] = [];
    global.fetch = vi.fn().mockImplementation((url) => {
      urls.push(url.toString());
      const payload = url.toString().includes("feasibility-check")
        ? { from_camera_id: "cam-01", to_camera_id: "cam-02", feasibility: "FEASIBLE" }
        : url.toString().includes("connectors")
          ? { items: [], total: 0, config_path: "config.json" }
          : { total_cameras: 30, geolocated_cameras: 0 };
      return Promise.resolve({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => payload,
      } as any);
    });

    await getCameraGapAnalysis(2500);
    await listVMSConnectors();
    await checkCameraPairFeasibility({ from_camera_id: "cam-01", to_camera_id: "cam-02", elapsed_seconds: 600 });

    expect(urls[0]).toContain("/api/v1/cameras/gap-analysis?isolation_radius_m=2500");
    expect(urls[1]).toContain("/api/v1/cameras/connectors");
    expect(urls[2]).toContain("/api/v1/routes/feasibility-check");
  });
});
