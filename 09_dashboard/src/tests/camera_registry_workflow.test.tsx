import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CameraRegistryTools } from "../components/cameras/CameraRegistryTools";
import type { Camera } from "../types/api";

const mocks = vi.hoisted(() => ({
  createCamera: vi.fn(),
  updateCamera: vi.fn(),
  bulkImportCameras: vi.fn(),
  getCameraGapAnalysis: vi.fn(),
  listVMSConnectors: vi.fn(),
  checkCameraPairFeasibility: vi.fn(),
}));

vi.mock("../api/cameras", () => ({
  analyzeCameraCoverage: vi.fn(),
  bulkImportCameras: mocks.bulkImportCameras,
  createCamera: mocks.createCamera,
  downloadCameraGapAnalysis: vi.fn().mockResolvedValue("gap.csv"),
  downloadCameraGeoJSON: vi.fn().mockResolvedValue("cameras.geojson"),
  getCameraGapAnalysis: mocks.getCameraGapAnalysis,
  listVMSConnectors: mocks.listVMSConnectors,
  syncVMSConnector: vi.fn(),
  updateCamera: mocks.updateCamera,
}));

vi.mock("../api/routes", () => ({
  checkCameraPairFeasibility: mocks.checkCameraPairFeasibility,
}));

const cameras: Camera[] = [
  { camera_id: "cam-01", name: "Camera One", latitude: 23.01, longitude: 72.51, location_quality: "VERIFIED", live: true, stream_status: "ONLINE" },
  { camera_id: "cam-02", name: "Camera Two", latitude: 23.02, longitude: 72.55, location_quality: "VERIFIED", live: true, stream_status: "ONLINE" },
];

describe("Camera setup and GIS workflow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getCameraGapAnalysis.mockResolvedValue({
      total_cameras: 2,
      geolocated_cameras: 2,
      verified_coordinates: 2,
      missing_stream_source: 0,
    });
    mocks.listVMSConnectors.mockResolvedValue({ items: [], total: 0, config_path: "test" });
    mocks.createCamera.mockResolvedValue({
      camera: { camera_id: "cam-03" },
      created: true,
      worker_status: "STARTED",
    });
  });

  it("requires coordinate provenance before registering GPS", async () => {
    const onChanged = vi.fn();
    render(<CameraRegistryTools cameras={cameras} selectedCamera={cameras[0]} canManage onChanged={onChanged} />);
    await screen.findByText("View organization integration readiness");

    fireEvent.click(screen.getByRole("button", { name: "Register camera" }));
    fireEvent.change(screen.getByLabelText("Camera ID"), { target: { value: "cam-03" } });
    fireEvent.change(screen.getByLabelText("Latitude"), { target: { value: "23.03" } });
    fireEvent.change(screen.getByLabelText("Longitude"), { target: { value: "72.58" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Register camera" })[1]);

    expect(await screen.findAllByText(/State the coordinate source/)).not.toHaveLength(0);
    expect(mocks.createCamera).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Coordinate source"), { target: { value: "Official survey record 42" } });
    fireEvent.change(screen.getByLabelText("Coordinate quality"), { target: { value: "VERIFIED" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Register camera" })[1]);

    await waitFor(() => expect(mocks.createCamera).toHaveBeenCalledWith(expect.objectContaining({
      camera_id: "cam-03",
      latitude: 23.03,
      longitude: 72.58,
      location_quality: "VERIFIED",
      coordinate_source: "Official survey record 42",
    })));
    expect(onChanged).toHaveBeenCalled();
  });

  it("runs the bounded camera-pair feasibility demonstration", async () => {
    mocks.checkCameraPairFeasibility.mockResolvedValue({
      from_camera_id: "cam-01",
      to_camera_id: "cam-02",
      elapsed_seconds: 600,
      distance_lower_bound_m: 4200,
      minimum_required_speed_kmh: 25.2,
      feasibility: "FEASIBLE",
      segment_score: 0.95,
      location_quality: "VERIFIED",
      warnings: [],
      explanation: "The lower-bound movement is physically plausible.",
      disclaimer: "Not a road route.",
    });

    render(<CameraRegistryTools cameras={cameras} selectedCamera={cameras[0]} canManage={false} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "GIS demonstration" }));
    fireEvent.click(screen.getByRole("button", { name: "Check feasibility" }));

    await waitFor(() => expect(mocks.checkCameraPairFeasibility).toHaveBeenCalledWith({
      from_camera_id: "cam-01",
      to_camera_id: "cam-02",
      elapsed_seconds: 600,
    }));
    expect(await screen.findByText("The lower-bound movement is physically plausible.")).toBeDefined();
    expect(screen.getByText("Not a road route.")).toBeDefined();
  });
});
