import { ApiError } from "../types/api";

const BASE_URL = import.meta.env.VITE_SENTINEL_API_URL || import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Module-level in-memory CSRF token store (never stored in localStorage or sessionStorage)
let _csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  _csrfToken = token;
}

export function getCsrfToken(): string | null {
  return _csrfToken;
}

export class ApiClientError extends Error {
  code: string;
  details?: any;
  status: number;

  constructor(message: string, code = "UNKNOWN_ERROR", status = 500, details?: any) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export class AuthenticationError extends ApiClientError {
  constructor(message = "Authentication required") {
    super(message, "AUTHENTICATION_REQUIRED", 401);
    this.name = "AuthenticationError";
  }
}

export class AuthorizationError extends ApiClientError {
  constructor(message = "Access denied: Insufficient permissions") {
    super(message, "ACCESS_DENIED", 403);
    this.name = "AuthorizationError";
  }
}

export async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  timeoutMs = 10000
): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const method = (options.method ?? "GET").toUpperCase();
  const isStateChanging = method !== "GET" && method !== "HEAD" && method !== "OPTIONS";

  const headers = new Headers(options.headers || {});

  // Automatically inject CSRF token for state-changing operations if available in memory
  if (isStateChanging && _csrfToken) {
    headers.set("X-CSRF-Token", _csrfToken);
  }

  if (!headers.has("Content-Type") && options.body && typeof options.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: "include", // ALWAYS send HttpOnly session cookie
      signal: options.signal || controller.signal,
    });

    clearTimeout(timeoutId);

    let data: any;
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      if (response.status === 401) {
        throw new AuthenticationError();
      }
      if (response.status === 403) {
        throw new AuthorizationError();
      }

      const errPayload = data as ApiError;
      const code = errPayload?.error?.code || `HTTP_${response.status}`;
      const msg =
        errPayload?.error?.message ||
        (typeof data === "object" && data?.detail ? String(data.detail) : undefined) ||
        (typeof data === "string" ? data : response.statusText);
      const details =
        errPayload?.error?.details ??
        (typeof data === "object" && data !== null ? data : undefined);
      throw new ApiClientError(msg, code, response.status, details);
    }

    return data as T;
  } catch (error: any) {
    clearTimeout(timeoutId);
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error.name === "AbortError") {
      throw new ApiClientError("Request timed out.", "TIMEOUT_ERROR", 408);
    }
    throw new ApiClientError(
      error.message || "Failed to communicate with SentinelTrack backend.",
      "NETWORK_ERROR",
      0
    );
  }
}

