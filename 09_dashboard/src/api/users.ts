import { request } from "./client";
import { UserRole } from "../types/auth";

export interface UserItem {
  user_id: string;
  username: string;
  display_name: string;
  role: UserRole;
  enabled: boolean;
  must_change_password: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string | null;
}

export interface UserListResponse {
  items: UserItem[];
  total: number;
}

export interface CreateUserPayload {
  username: string;
  display_name: string;
  password: string;
  role: UserRole;
  must_change_password?: boolean;
}

export interface UpdateUserPayload {
  display_name?: string;
  role?: UserRole;
  enabled?: boolean;
  must_change_password?: boolean;
}

export async function listUsers(params?: { limit?: number; offset?: number }): Promise<UserListResponse> {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) query.append("limit", String(params.limit));
  if (params?.offset !== undefined) query.append("offset", String(params.offset));
  const qs = query.toString();
  return request<UserListResponse>(`/api/v1/users${qs ? `?${qs}` : ""}`);
}

export async function createUser(data: CreateUserPayload): Promise<UserItem> {
  return request<UserItem>("/api/v1/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateUser(userId: string, data: UpdateUserPayload): Promise<UserItem> {
  return request<UserItem>(`/api/v1/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function resetUserPassword(userId: string, newPassword: string): Promise<UserItem> {
  return request<UserItem>(`/api/v1/users/${encodeURIComponent(userId)}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword, must_change_password: true }),
  });
}
