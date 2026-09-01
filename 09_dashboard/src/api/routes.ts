import { request } from "./client";
import {
  RouteResponse,
  RouteSummaryResponse,
  GeoJSONFeatureCollection,
} from "../types/api";

const BASE_URL = import.meta.env.VITE_SENTINEL_API_URL || import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function getVehicleRoute(
  registration: string,
  params?: {
    start_time?: string;
    end_time?: string;
    min_match_score?: number;
  }
): Promise<RouteResponse> {
  const query = new URLSearchParams();
  if (params?.start_time) query.append("start_time", params.start_time);
  if (params?.end_time) query.append("end_time", params.end_time);
  if (params?.min_match_score !== undefined) query.append("min_match_score", String(params.min_match_score));

  const qs = query.toString();
  return request<RouteResponse>(`/api/v1/routes/${encodeURIComponent(registration)}${qs ? `?${qs}` : ""}`);
}

export async function getVehicleRouteGeoJSON(
  registration: string,
  params?: {
    start_time?: string;
    end_time?: string;
    min_match_score?: number;
  }
): Promise<GeoJSONFeatureCollection> {
  const query = new URLSearchParams();
  if (params?.start_time) query.append("start_time", params.start_time);
  if (params?.end_time) query.append("end_time", params.end_time);
  if (params?.min_match_score !== undefined) query.append("min_match_score", String(params.min_match_score));

  const qs = query.toString();
  return request<GeoJSONFeatureCollection>(`/api/v1/routes/${encodeURIComponent(registration)}/geojson${qs ? `?${qs}` : ""}`);
}

export async function getVehicleRouteSummary(
  registration: string,
  params?: {
    start_time?: string;
    end_time?: string;
    min_match_score?: number;
  }
): Promise<RouteSummaryResponse> {
  const query = new URLSearchParams();
  if (params?.start_time) query.append("start_time", params.start_time);
  if (params?.end_time) query.append("end_time", params.end_time);
  if (params?.min_match_score !== undefined) query.append("min_match_score", String(params.min_match_score));

  const qs = query.toString();
  return request<RouteSummaryResponse>(`/api/v1/routes/${encodeURIComponent(registration)}/summary${qs ? `?${qs}` : ""}`);
}

export async function downloadVehicleRouteReport(registration: string): Promise<string> {
  const response = await fetch(
    `${BASE_URL}/api/v1/routes/${encodeURIComponent(registration)}/report.csv`,
    { credentials: "include", cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Report download failed (HTTP ${response.status})`);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  const filename = filenameMatch?.[1] || `sentineltrack_${registration.toUpperCase()}_report.csv`;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return filename;
}
