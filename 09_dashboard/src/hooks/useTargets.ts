import { useState, useEffect, useCallback } from "react";
import { listTargets, createTarget, updateTarget, disableTarget } from "../api/targets";
import { Target, TargetCreateRequest, TargetUpdateRequest } from "../types/api";

export function useTargets(params?: { enabled?: boolean; priority?: string }, enabled = true) {
  const [targets, setTargets] = useState<Target[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTargets = useCallback(async () => {
    if (!enabled) {
      setTargets([]);
      setTotal(0);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const res = await listTargets({
        enabled: params?.enabled,
        priority: params?.priority,
      });
      setTargets(res.items);
      setTotal(res.total);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Failed to load target watchlists");
    } finally {
      setLoading(false);
    }
  }, [params?.enabled, params?.priority, enabled]);

  useEffect(() => {
    fetchTargets();
  }, [fetchTargets]);

  const handleCreate = async (data: TargetCreateRequest): Promise<Target> => {
    const created = await createTarget(data);
    await fetchTargets();
    return created;
  };

  const handleUpdate = async (targetId: string, data: TargetUpdateRequest): Promise<Target> => {
    const updated = await updateTarget(targetId, data);
    await fetchTargets();
    return updated;
  };

  const handleDisable = async (targetId: string): Promise<Target> => {
    const disabled = await disableTarget(targetId);
    await fetchTargets();
    return disabled;
  };

  return { targets, total, loading, error, refresh: fetchTargets, create: handleCreate, update: handleUpdate, disable: handleDisable };
}
