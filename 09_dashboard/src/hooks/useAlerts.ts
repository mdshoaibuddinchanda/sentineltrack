import { useState, useEffect, useCallback } from "react";
import { listAlerts, acknowledgeAlert } from "../api/alerts";
import { Alert } from "../types/api";
import { DEMO_ALERTS } from "../utils/demoData";

export function useAlerts(params?: { unacknowledged?: boolean; limit?: number }, demoMode = false) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [total, setTotal] = useState(0);
  const [unackCount, setUnackCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    if (demoMode) {
      let items = [...DEMO_ALERTS];
      if (params?.unacknowledged) items = items.filter((a) => !a.acknowledged);
      setAlerts(items);
      setTotal(items.length);
      setUnackCount(DEMO_ALERTS.filter((a) => !a.acknowledged).length);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const res = await listAlerts(params);
      setAlerts(res.items);
      setTotal(res.total);
      setUnackCount(res.unacknowledged_count);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Failed to fetch alerts");
    } finally {
      setLoading(false);
    }
  }, [params?.unacknowledged, params?.limit, demoMode]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const handleAcknowledge = async (alertId: string, operator = "operator") => {
    // Optimistic UI update
    const previousAlerts = [...alerts];
    setAlerts((prev) =>
      prev.map((a) =>
        a.alert_id === alertId
          ? { ...a, acknowledged: true, acknowledged_by: operator, acknowledged_at: new Date().toISOString() }
          : a
      )
    );
    setUnackCount((prev) => Math.max(0, prev - 1));

    if (demoMode) return;

    try {
      await acknowledgeAlert(alertId, operator);
    } catch (e: any) {
      // Rollback on failure
      setAlerts(previousAlerts);
      setUnackCount((prev) => prev + 1);
      throw e;
    }
  };

  const prependLiveAlert = useCallback((liveAlert: Alert) => {
    setAlerts((prev) => {
      const exists = prev.some((a) => a.alert_id === liveAlert.alert_id);
      if (exists) return prev;
      if (!liveAlert.acknowledged) {
        setUnackCount((c) => c + 1);
      }
      setTotal((t) => t + 1);
      return [liveAlert, ...prev];
    });
  }, []);

  return { alerts, total, unackCount, loading, error, refresh: fetchAlerts, acknowledge: handleAcknowledge, prependLiveAlert };
}
