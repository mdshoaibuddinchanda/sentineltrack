import { request } from "./client";
import {
  SightingListResponse,
  VehicleHistoryResponse,
} from "../types/api";

export async function listSightings(params?: {
  registration?: string;
  camera_id?: string;
  start_time?: string;
  end_time?: string;
  min_score?: number;
  limit?: number;
  offset?: number;
}): Promise<SightingListResponse> {
  const query = new URLSearchParams();
  if (params?.registration) query.append("registration", params.registration);
  if (params?.camera_id) query.append("camera_id", params.camera_id);
  if (params?.start_time) query.append("start_time", params.start_time);
  if (params?.end_time) query.append("end_time", params.end_time);
  if (params?.min_score !== undefined) query.append("min_score", String(params.min_score));
  if (params?.limit !== undefined) query.append("limit", String(params.limit));
  if (params?.offset !== undefined) query.append("offset", String(params.offset));

  const qs = query.toString();
  return request<SightingListResponse>(`/api/v1/sightings${qs ? `?${qs}` : ""}`);
}

export async function getVehicleHistory(registration: string): Promise<VehicleHistoryResponse> {
  return request<VehicleHistoryResponse>(`/api/v1/vehicles/${encodeURIComponent(registration)}/history`);
}
