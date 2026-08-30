import { useState, useEffect, useCallback } from "react";
import { listCameras } from "../api/cameras";
import { Camera } from "../types/api";

export function useCameras(params?: { department?: string; live?: boolean; stream_status?: string }, enabled = true) {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCameras = useCallback(async () => {
    if (!enabled) {
      setCameras([]);
      setTotal(0);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const res = await listCameras({
        department: params?.department,
        live: params?.live,
        stream_status: params?.stream_status,
      });
      setCameras(res.items);
      setTotal(res.total);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Failed to load camera registry");
    } finally {
      setLoading(false);
    }
  }, [params?.department, params?.live, params?.stream_status, enabled]);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  return { cameras, total, loading, error, refresh: fetchCameras };
}
