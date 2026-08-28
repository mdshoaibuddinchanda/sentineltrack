import type { AuthUser, LoginResponse, CsrfResponse } from '../types/auth';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Module-level CSRF token store (never persisted to localStorage)
// ---------------------------------------------------------------------------
let _csrfToken: string | null = null;

export function setCsrfToken(token: string): void {
  _csrfToken = token;
}

export function getCsrfToken(): string | null {
  return _csrfToken;
}

// ---------------------------------------------------------------------------
// Custom error types
// ---------------------------------------------------------------------------

export class AuthenticationError extends Error {
  constructor(message = 'Authentication required') {
    super(message);
    this.name = 'AuthenticationError';
  }
}

// ---------------------------------------------------------------------------
// Core fetch helper
// ---------------------------------------------------------------------------

/**
 * Wrapper around fetch that:
 * - Always sends credentials (HttpOnly cookie)
 * - Injects X-CSRF-Token for state-changing methods (POST/PATCH/DELETE/PUT)
 * - Throws AuthenticationError on 401
 * - Throws Error on 403 and other non-OK responses
 */
export async function authedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const method = (options.method ?? 'GET').toUpperCase();
  const isStateChanging =
    method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS';

  const headers = new Headers(options.headers);

  if (isStateChanging && _csrfToken) {
    headers.set('X-CSRF-Token', _csrfToken);
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
    throw new Error('Access denied: Insufficient permissions');
  }

  // Try to extract a meaningful error message from the response body
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

// ---------------------------------------------------------------------------
// Auth API functions
// ---------------------------------------------------------------------------

/**
 * Fetches a fresh CSRF token from the server and stores it in the module.
 * Safe to call on page load — the session cookie determines the session context.
 */
export async function fetchCsrfToken(): Promise<string> {
  const response = await fetch(`${API_BASE}/api/v1/auth/csrf`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch CSRF token: ${response.statusText}`);
  }

  const data: CsrfResponse = await response.json();
  _csrfToken = data.csrf_token;
  return data.csrf_token;
}

/**
 * Authenticates the user via username + password.
 * On success, stores the returned CSRF token in the module.
 * Throws a descriptive Error on HTTP failures.
 */
export async function login(
  username: string,
  password: string
): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
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

  const data: LoginResponse = await response.json();
  setCsrfToken(data.csrf_token);
  return data;
}

/**
 * Logs the current user out. Sends CSRF token in header, then clears the
 * module store regardless of server response.
 */
export async function logout(): Promise<void> {
  try {
    await authedFetch(`${API_BASE}/api/v1/auth/logout`, {
      method: 'POST',
    });
  } finally {
    // Always clear the local token even if the request fails
    _csrfToken = null;
  }
}

/**
 * Returns the currently authenticated user's profile including permissions.
 * Throws AuthenticationError on 401.
 */
export async function getMe(): Promise<AuthUser> {
  const response = await authedFetch(`${API_BASE}/api/v1/auth/me`, {
    method: 'GET',
  });

  const data: AuthUser = await response.json();
  return data;
}
