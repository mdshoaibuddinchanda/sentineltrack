import { request } from "./client";
import {
  Camera,
  CameraListResponse,
  CameraHealth,
} from "../types/api";

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
