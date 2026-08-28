import { useState, useEffect, useCallback } from "react";
import { listCameras } from "../api/cameras";
import { Camera } from "../types/api";
import { DEMO_CAMERAS } from "../utils/demoData";

export function useCameras(params?: { department?: string; live?: boolean; stream_status?: string }, demoMode = false) {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCameras = useCallback(async () => {
    if (demoMode) {
      let items = [...DEMO_CAMERAS];
      if (params?.department) items = items.filter((c) => c.department?.toLowerCase().includes(params.department!.toLowerCase()));
      if (params?.stream_status) items = items.filter((c) => c.stream_status === params.stream_status);
      setCameras(items);
      setTotal(items.length);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const res = await listCameras(params);
      setCameras(res.items);
      setTotal(res.total);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Failed to load camera registry");
    } finally {
      setLoading(false);
    }
  }, [params?.department, params?.live, params?.stream_status, demoMode]);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  return { cameras, total, loading, error, refresh: fetchCameras };
}
