export type UserRole = 'ADMIN' | 'SUPERVISOR' | 'OPERATOR' | 'AUDITOR';

export interface AuthUser {
  user_id: string;
  username: string;
  role: UserRole;
  permissions: string[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  user_id: string;
  username: string;
  role: UserRole;
  csrf_token: string;
}

export interface CsrfResponse {
  csrf_token: string;
}
