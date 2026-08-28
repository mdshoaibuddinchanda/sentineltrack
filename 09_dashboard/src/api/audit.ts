import { request } from "./client";

export interface AuditEventItem {
  event_id: string;
  timestamp: string;
  action: string;
  actor_id?: string | null;
  actor_username?: string | null;
  actor_role?: string | null;
  resource_type: string;
  resource_id?: string | null;
  outcome: string;
  source_ip?: string | null;
  request_id?: string | null;
  details?: Record<string, any> | null;
}

export interface AuditListResponse {
  items: AuditEventItem[];
  total: number;
}

export async function listAuditEvents(params?: {
  action?: string;
  actor_id?: string;
  resource_type?: string;
  outcome?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditListResponse> {
  const query = new URLSearchParams();
  if (params?.action) query.append("action", params.action);
  if (params?.actor_id) query.append("actor_id", params.actor_id);
  if (params?.resource_type) query.append("resource_type", params.resource_type);
  if (params?.outcome) query.append("outcome", params.outcome);
  if (params?.limit !== undefined) query.append("limit", String(params.limit));
  if (params?.offset !== undefined) query.append("offset", String(params.offset));
  const qs = query.toString();
  return request<AuditListResponse>(`/api/v1/audit${qs ? `?${qs}` : ""}`);
}
