import { ApiError } from "../types/api";

const BASE_URL = import.meta.env.VITE_SENTINEL_API_URL || "http://localhost:8000";

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

export async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  timeoutMs = 10000
): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && typeof options.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
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
      const errPayload = data as ApiError;
      const code = errPayload?.error?.code || `HTTP_${response.status}`;
      const msg = errPayload?.error?.message || (typeof data === "string" ? data : response.statusText);
      throw new ApiClientError(msg, code, response.status, errPayload?.error?.details);
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
