import { request } from "./client";
import {
  Alert,
  AlertListResponse,
  AlertAckResponse,
} from "../types/api";

export async function listAlerts(params?: {
  unacknowledged?: boolean;
  camera_id?: string;
  severity?: string;
  limit?: number;
  offset?: number;
}): Promise<AlertListResponse> {
  const query = new URLSearchParams();
  if (params?.unacknowledged !== undefined) query.append("unacknowledged", String(params.unacknowledged));
  if (params?.camera_id) query.append("camera_id", params.camera_id);
  if (params?.severity) query.append("severity", params.severity);
  if (params?.limit !== undefined) query.append("limit", String(params.limit));
  if (params?.offset !== undefined) query.append("offset", String(params.offset));

  const qs = query.toString();
  return request<AlertListResponse>(`/api/v1/alerts${qs ? `?${qs}` : ""}`);
}

export async function getAlert(alertId: string): Promise<Alert> {
  return request<Alert>(`/api/v1/alerts/${encodeURIComponent(alertId)}`);
}

export async function acknowledgeAlert(alertId: string, acknowledgedBy = "operator"): Promise<AlertAckResponse> {
  return request<AlertAckResponse>(`/api/v1/alerts/${encodeURIComponent(alertId)}/ack`, {
    method: "POST",
    body: JSON.stringify({ acknowledged_by: acknowledgedBy }),
  });
}
