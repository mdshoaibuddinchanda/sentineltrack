import { request } from "./client";
import {
  RouteResponse,
  RouteSummaryResponse,
  GeoJSONFeatureCollection,
} from "../types/api";

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
