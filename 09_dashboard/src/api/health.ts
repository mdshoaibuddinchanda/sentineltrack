import { request } from "./client";
import {
  HealthResponse,
  ReadinessResponse,
  MetricsResponse,
} from "../types/api";

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function getReadiness(): Promise<ReadinessResponse> {
  return request<ReadinessResponse>("/ready");
}

export async function getMetrics(): Promise<MetricsResponse> {
  return request<MetricsResponse>("/metrics");
}
