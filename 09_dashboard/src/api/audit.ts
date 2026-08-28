import { request } from "./client";

export interface AuditEventItem {
  audit_id: string;
  event_time_utc: string;
  actor_user_id?: string | null;
  actor_username?: string | null;
  actor_role?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  outcome: string;
  request_id?: string | null;
  source_ip?: string | null;
  user_agent?: string | null;
  details?: Record<string, unknown> | null;
}

export interface AuditListResponse {
  items: AuditEventItem[];
  total: number;
}

export async function listAuditEvents(params?: {
  actor_username?: string;
  action?: string;
  resource_type?: string;
  outcome?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditListResponse> {
  const query = new URLSearchParams();
  if (params?.actor_username) query.append("actor_username", params.actor_username);
  if (params?.action) query.append("action", params.action);
  if (params?.resource_type) query.append("resource_type", params.resource_type);
  if (params?.outcome) query.append("outcome", params.outcome);
  if (params?.limit !== undefined) query.append("limit", String(params.limit));
  if (params?.offset !== undefined) query.append("offset", String(params.offset));
  const qs = query.toString();
  return request<AuditListResponse>(`/api/v1/audit${qs ? `?${qs}` : ""}`);
}
