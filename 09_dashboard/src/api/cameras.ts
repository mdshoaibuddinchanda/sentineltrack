import { request } from "./client";
import {
  Camera,
  CameraListResponse,
  CameraHealth,
  CameraRegistryInput,
  CameraUpdateRequest,
  CameraMutationResponse,
  CameraImportMode,
  CameraBulkImportResponse,
  CameraGapAnalysisResponse,
  CoverageAnalysisResponse,
  VMSConnectorListResponse,
} from "../types/api";

const BASE_URL = import.meta.env.VITE_SENTINEL_API_URL || import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function getCameraPreviewUrl(cameraId: string, cacheKey = Date.now()): string {
  return `${BASE_URL}/api/v1/cameras/${encodeURIComponent(cameraId)}/preview?ts=${cacheKey}`;
}

export function getCameraLiveStreamUrl(cameraId: string, cacheKey = Date.now()): string {
  return `${BASE_URL}/api/v1/cameras/${encodeURIComponent(cameraId)}/live?session=${cacheKey}`;
}

export async function fetchCameraPreview(cameraId: string, signal?: AbortSignal): Promise<Blob> {
  const response = await fetch(getCameraPreviewUrl(cameraId), {
    credentials: "include",
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new Error(`Camera preview unavailable (HTTP ${response.status})`);
  }
  return response.blob();
}

export async function listCameras(params?: {
  department?: string;
  live?: boolean;
  stream_status?: string;
  limit?: number;
  offset?: number;
}): Promise<CameraListResponse> {
  const query = new URLSearchParams();
  if (params?.department) query.append("department", params.department);
  if (params?.live !== undefined) query.append("live", String(params.live));
  if (params?.stream_status) query.append("stream_status", params.stream_status);
  if (params?.limit !== undefined) query.append("limit", String(params.limit));
  if (params?.offset !== undefined) query.append("offset", String(params.offset));

  const qs = query.toString();
  return request<CameraListResponse>(`/api/v1/cameras${qs ? `?${qs}` : ""}`);
}

export async function getCamera(cameraId: string): Promise<Camera> {
  return request<Camera>(`/api/v1/cameras/${encodeURIComponent(cameraId)}`);
}

export async function getCameraHealth(cameraId: string): Promise<CameraHealth> {
  return request<CameraHealth>(`/api/v1/cameras/${encodeURIComponent(cameraId)}/health`);
}

export async function searchNearbyCameras(
  lat: number,
  lon: number,
  radiusM = 5000
): Promise<Camera[]> {
  const query = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    radius_m: String(radiusM),
  });
  return request<Camera[]>(`/api/v1/cameras/nearby?${query.toString()}`);
}

export async function getNearbyCamerasForCamera(
  cameraId: string,
  radiusM = 5000
): Promise<Camera[]> {
  const query = new URLSearchParams({
    radius_m: String(radiusM),
  });
  return request<Camera[]>(`/api/v1/cameras/${encodeURIComponent(cameraId)}/nearby?${query.toString()}`);
}

export async function createCamera(payload: CameraRegistryInput): Promise<CameraMutationResponse> {
  return request<CameraMutationResponse>("/api/v1/cameras", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateCamera(
  cameraId: string,
  payload: CameraUpdateRequest,
): Promise<CameraMutationResponse> {
  return request<CameraMutationResponse>(`/api/v1/cameras/${encodeURIComponent(cameraId)}/registry`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function bulkImportCameras(
  cameras: CameraRegistryInput[],
  options: { mode: CameraImportMode; dry_run: boolean },
): Promise<CameraBulkImportResponse> {
  return request<CameraBulkImportResponse>("/api/v1/cameras/bulk", {
    method: "POST",
    body: JSON.stringify({ cameras, ...options }),
  }, 30000);
}

export async function getCameraGapAnalysis(isolationRadiusM = 5000): Promise<CameraGapAnalysisResponse> {
  const query = new URLSearchParams({ isolation_radius_m: String(isolationRadiusM) });
  return request<CameraGapAnalysisResponse>(`/api/v1/cameras/gap-analysis?${query.toString()}`);
}

export async function analyzeCameraCoverage(payload: {
  area_of_interest: Record<string, unknown>;
  default_coverage_radius_m: number;
  include_approximate: boolean;
}): Promise<CoverageAnalysisResponse> {
  return request<CoverageAnalysisResponse>("/api/v1/cameras/coverage-analysis", {
    method: "POST",
    body: JSON.stringify(payload),
  }, 30000);
}

export async function listVMSConnectors(): Promise<VMSConnectorListResponse> {
  return request<VMSConnectorListResponse>("/api/v1/cameras/connectors");
}

export async function syncVMSConnector(
  connectorId: string,
  options: { mode: CameraImportMode; dry_run: boolean },
): Promise<CameraBulkImportResponse> {
  return request<CameraBulkImportResponse>(
    `/api/v1/cameras/connectors/${encodeURIComponent(connectorId)}/sync`,
    { method: "POST", body: JSON.stringify(options) },
    60000,
  );
}

async function downloadCameraArtifact(path: string, fallbackFilename: string): Promise<string> {
  const response = await fetch(`${BASE_URL}${path}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Camera registry export failed (HTTP ${response.status})`);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  const filename = filenameMatch?.[1] || fallbackFilename;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return filename;
}

export function downloadCameraGapAnalysis(isolationRadiusM = 5000): Promise<string> {
  const query = new URLSearchParams({ isolation_radius_m: String(isolationRadiusM) });
  return downloadCameraArtifact(
    `/api/v1/cameras/gap-analysis.csv?${query.toString()}`,
    "sentineltrack_camera_gap_analysis.csv",
  );
}

export function downloadCameraGeoJSON(): Promise<string> {
  return downloadCameraArtifact("/api/v1/cameras/export.geojson", "sentineltrack_cameras.geojson");
}
