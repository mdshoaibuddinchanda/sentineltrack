import { useState, useEffect, useCallback } from "react";
import { getHealth, getReadiness, getMetrics } from "../api/health";
import { HealthResponse, ReadinessResponse, MetricsSnapshot } from "../types/api";

export type SystemStatusType = "HEALTHY" | "DEGRADED" | "OFFLINE" | "LOADING";

export function useSystemStatus(pollIntervalMs = 8000, enabled = true) {
  const [status, setStatus] = useState<SystemStatusType>("LOADING");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!enabled) {
      setStatus("LOADING");
      setHealth(null);
      setReadiness(null);
      setMetrics(null);
      setError(null);
      return;
    }
    try {
      const [h, r, m] = await Promise.all([
        getHealth().catch(() => null),
        getReadiness().catch((err) => {
          if (err?.status === 503) {
            return {
              status: "degraded" as const,
              components: err?.details?.components || {},
              details: err?.details || {},
            };
          }
          return null;
        }),
        getMetrics().catch(() => null),
      ]);

      const coreComponents = Object.entries(r?.components || {})
        .filter(([key]) => key !== "stream_ingestion")
        .map(([, value]) => value);

      if (!h) {
        setStatus("OFFLINE");
        setError("SentinelTrack backend is unreachable.");
      } else if (coreComponents.some((value) => value === false)) {
        setStatus("DEGRADED");
        setError(null);
      } else {
        setStatus("HEALTHY");
        setError(null);
      }

      setHealth(h);
      setReadiness(r);
      if (m?.metrics) setMetrics(m.metrics);
      setLastUpdated(new Date());
    } catch (e: any) {
      setStatus("OFFLINE");
      setError(e.message || "Failed to poll system status");
    }
  }, [enabled]);

  useEffect(() => {
    fetchStatus();
    if (!enabled) return;
    const interval = setInterval(fetchStatus, pollIntervalMs);
    return () => clearInterval(interval);
  }, [fetchStatus, pollIntervalMs, enabled]);

  return { status, health, readiness, metrics, lastUpdated, error, refresh: fetchStatus };
}
