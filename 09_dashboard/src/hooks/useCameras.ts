import { useState, useEffect, useCallback, useRef } from "react";
import { listCameras } from "../api/cameras";
import { Camera } from "../types/api";

export function useCameras(params?: { department?: string; live?: boolean; stream_status?: string }, enabled = true) {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);

  const fetchCameras = useCallback(async () => {
    if (!enabled) {
      setCameras([]);
      setTotal(0);
      setLoading(false);
      hasLoadedRef.current = false;
      return;
    }
    try {
      if (!hasLoadedRef.current) setLoading(true);
      const res = await listCameras({
        department: params?.department,
        live: params?.live,
        stream_status: params?.stream_status,
      });
      setCameras(res.items);
      setTotal(res.total);
      setError(null);
      hasLoadedRef.current = true;
    } catch (e: any) {
      setError(e.message || "Failed to load camera registry");
    } finally {
      setLoading(false);
    }
  }, [params?.department, params?.live, params?.stream_status, enabled]);

  useEffect(() => {
    fetchCameras();
    if (!enabled) return;
    const interval = window.setInterval(fetchCameras, 5000);
    return () => window.clearInterval(interval);
  }, [fetchCameras, enabled]);

  return { cameras, total, loading, error, refresh: fetchCameras };
}
