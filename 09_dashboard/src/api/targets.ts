import { request } from "./client";
import {
  Target,
  TargetListResponse,
  TargetCreateRequest,
  TargetUpdateRequest,
} from "../types/api";

export async function listTargets(params?: {
  enabled?: boolean;
  priority?: string;
  limit?: number;
  offset?: number;
}): Promise<TargetListResponse> {
  const query = new URLSearchParams();
  if (params?.enabled !== undefined) query.append("enabled", String(params.enabled));
  if (params?.priority) query.append("priority", params.priority);
  if (params?.limit !== undefined) query.append("limit", String(params.limit));
  if (params?.offset !== undefined) query.append("offset", String(params.offset));

  const qs = query.toString();
  return request<TargetListResponse>(`/api/v1/targets${qs ? `?${qs}` : ""}`);
}

export async function getTarget(targetId: string): Promise<Target> {
  return request<Target>(`/api/v1/targets/${encodeURIComponent(targetId)}`);
}

export async function createTarget(data: TargetCreateRequest): Promise<Target> {
  return request<Target>("/api/v1/targets", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTarget(targetId: string, data: TargetUpdateRequest): Promise<Target> {
  return request<Target>(`/api/v1/targets/${encodeURIComponent(targetId)}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function disableTarget(targetId: string): Promise<Target> {
  return request<Target>(`/api/v1/targets/${encodeURIComponent(targetId)}`, {
    method: "DELETE",
  });
}
