import type { AuthUser, LoginResponse, CsrfResponse } from '../types/auth';
import {
  request,
  setCsrfToken,
  getCsrfToken,
  AuthenticationError,
  AuthorizationError,
} from './client';

export { setCsrfToken, getCsrfToken, AuthenticationError, AuthorizationError };

/**

 * Fetches a fresh CSRF token from the server and stores it in memory.
 * Safe to call on page load — the session cookie determines the session context.
 */
export async function fetchCsrfToken(): Promise<string> {
  const data = await request<CsrfResponse>('/api/v1/auth/csrf');
  setCsrfToken(data.csrf_token);
  return data.csrf_token;
}

/**
 * Authenticates the user via username + password.
 * On success, stores the returned CSRF token in memory.
 */
export async function login(
  username: string,
  password: string
): Promise<LoginResponse> {
  const data = await request<LoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  setCsrfToken(data.csrf_token);
  return data;
}

/**
 * Logs the current user out. Sends CSRF token in header, then clears the
 * memory store regardless of server response.
 */
export async function logout(): Promise<void> {
  try {
    await request<{ message: string }>('/api/v1/auth/logout', {
      method: 'POST',
    });
  } finally {
    setCsrfToken(null);
  }
}

/**
 * Returns the currently authenticated user's profile including permissions.
 * Throws AuthenticationError on 401.
 */
export async function getMe(): Promise<AuthUser> {
  const data = await request<{ user: AuthUser; role: string; permissions: string[] }>('/api/v1/auth/me');
  return {
    ...data.user,
    permissions: data.permissions,
  };
}

/**
 * Legacy wrapper for fetch with credentials and CSRF support (for custom calls).
 */
export async function authedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const method = (options.method ?? 'GET').toUpperCase();
  const isStateChanging =
    method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS';

  const headers = new Headers(options.headers);
  const token = getCsrfToken();
  if (isStateChanging && token) {
    headers.set('X-CSRF-Token', token);
  }

  if (!headers.has('Content-Type') && isStateChanging) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (response.ok) {
    return response;
  }

  if (response.status === 401) {
    throw new AuthenticationError();
  }

  if (response.status === 403) {
    throw new AuthorizationError();
  }

  let errorMessage: string;
  try {
    const body = await response.json();
    errorMessage =
      body?.error?.message ??
      body?.detail ??
      body?.message ??
      response.statusText;
  } catch {
    errorMessage = response.statusText || `HTTP ${response.status}`;
  }

  throw new Error(errorMessage);
}

