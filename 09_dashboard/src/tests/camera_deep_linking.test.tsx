import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { CamerasPage } from "../pages/CamerasPage";
import { hasValidCameraCoordinates } from "../components/map/ControlRoomMap";
import { Camera } from "../types/api";

vi.mock("../api/cameras", () => ({
  searchNearbyCameras: vi.fn().mockResolvedValue([]),
  getCameraLiveStreamUrl: vi.fn((cameraId: string) => `/live/${cameraId}`),
  getCameraPreviewUrl: vi.fn((cameraId: string) => `/preview/${cameraId}`),
  getCameraGapAnalysis: vi.fn().mockResolvedValue({
    total_cameras: 2,
    geolocated_cameras: 2,
    verified_coordinates: 2,
    missing_stream_source: 0,
  }),
  listVMSConnectors: vi.fn().mockResolvedValue({ items: [], total: 0, config_path: "test" }),
  downloadCameraGapAnalysis: vi.fn(),
  downloadCameraGeoJSON: vi.fn(),
}));

describe("Camera Deep Linking & Asynchronous Loading Tests", () => {
  it("rejects null or non-finite camera coordinates before map rendering", () => {
    expect(hasValidCameraCoordinates({ latitude: null, longitude: 72.5 })).toBe(false);
    expect(hasValidCameraCoordinates({ latitude: 23.0, longitude: Number.NaN })).toBe(false);
    expect(hasValidCameraCoordinates({ latitude: 23.0, longitude: 72.5 })).toBe(true);
  });

  const mockCameras: Camera[] = [
    {
      camera_id: "cam_sg_highway_01",
      name: "SG Highway Junction",
      department: "Traffic Police",
      stream_status: "ONLINE",
      measured_fps: 29.8,
      location_quality: "VERIFIED",
      latitude: 23.0305,
      longitude: 72.5075,
      azimuth: 180,
      live: true,
    },
    {
      camera_id: "cam_vastrapur_01",
      name: "Vastrapur Lake East",
      department: "Urban Security",
      stream_status: "ONLINE",
      measured_fps: 30.0,
      location_quality: "VERIFIED",
      latitude: 23.0381,
      longitude: 72.5292,
      azimuth: 90,
      live: true,
    },
  ];

  it("shows every camera in the default overview", async () => {
    render(
      <MemoryRouter initialEntries={["/cameras"]}>
        <Routes>
          <Route path="/cameras" element={<CamerasPage cameras={mockCameras} />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("All cameras (2)")).toBeDefined();
      expect(screen.getAllByRole("button", { name: /Open camera/ })).toHaveLength(2);
    });
  });

  it("selects requested camera from route URL parameter", async () => {
    render(
      <MemoryRouter initialEntries={["/cameras/cam_vastrapur_01"]}>
        <Routes>
          <Route
            path="/cameras/:cameraId"
            element={<CamerasPage cameras={mockCameras} />}
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText("Vastrapur Lake East").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Urban Security").length).toBeGreaterThan(0);
    });
  });

  it("asynchronously synchronizes camera selection once camera list arrives", async () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={["/cameras/cam_vastrapur_01"]}>
        <Routes>
          <Route
            path="/cameras/:cameraId"
            element={<CamerasPage cameras={[]} />}
          />
        </Routes>
      </MemoryRouter>
    );

    // Initial render with empty cameras list
    expect(screen.getByText("Camera 'cam_vastrapur_01' not found")).toBeDefined();

    // Cameras list arrives from backend
    rerender(
      <MemoryRouter initialEntries={["/cameras/cam_vastrapur_01"]}>
        <Routes>
          <Route
            path="/cameras/:cameraId"
            element={<CamerasPage cameras={mockCameras} />}
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText("Vastrapur Lake East").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Urban Security").length).toBeGreaterThan(0);
    });
  });

  it("displays truthful not-found state when requested camera ID does not exist", async () => {
    render(
      <MemoryRouter initialEntries={["/cameras/cam_nonexistent_999"]}>
        <Routes>
          <Route
            path="/cameras/:cameraId"
            element={<CamerasPage cameras={mockCameras} />}
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Camera 'cam_nonexistent_999' not found")).toBeDefined();
      expect(screen.getByText("This camera ID is not registered in the CCTV network.")).toBeDefined();
    });
  });
});
