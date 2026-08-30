import { useState, useEffect, useCallback } from "react";
import { listTargets, createTarget, updateTarget, disableTarget } from "../api/targets";
import { Target, TargetCreateRequest, TargetUpdateRequest } from "../types/api";
import { DEMO_TARGETS } from "../utils/demoData";

export function useTargets(params?: { enabled?: boolean; priority?: string }, demoMode = false, enabled = true) {
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
    if (demoMode) {
      let items = [...DEMO_TARGETS];
      if (params?.enabled !== undefined) items = items.filter((t) => t.enabled === params.enabled);
      if (params?.priority) items = items.filter((t) => t.priority === params.priority);
      setTargets(items);
      setTotal(items.length);
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
  }, [params?.enabled, params?.priority, demoMode, enabled]);

  useEffect(() => {
    fetchTargets();
  }, [fetchTargets]);

  const handleCreate = async (data: TargetCreateRequest): Promise<Target> => {
    if (demoMode) {
      const newTgt: Target = {
        target_id: `tgt_demo_${Date.now()}`,
        registration: data.registration.trim().toUpperCase(),
        normalized_registration: data.registration.trim().toUpperCase().replace(/\s+/g, ""),
        priority: data.priority || "NORMAL",
        enabled: true,
        created_at: new Date().toISOString(),
        notes: data.notes,
        metadata: data.metadata,
      };
      setTargets((prev) => [newTgt, ...prev]);
      setTotal((prev) => prev + 1);
      return newTgt;
    }

    const created = await createTarget(data);
    await fetchTargets();
    return created;
  };

  const handleUpdate = async (targetId: string, data: TargetUpdateRequest): Promise<Target> => {
    if (demoMode) {
      setTargets((prev) =>
        prev.map((t) => (t.target_id === targetId ? { ...t, ...data, priority: data.priority || t.priority } : t))
      );
      return targets.find((t) => t.target_id === targetId)!;
    }

    const updated = await updateTarget(targetId, data);
    await fetchTargets();
    return updated;
  };

  const handleDisable = async (targetId: string): Promise<Target> => {
    if (demoMode) {
      setTargets((prev) => prev.map((t) => (t.target_id === targetId ? { ...t, enabled: false } : t)));
      return targets.find((t) => t.target_id === targetId)!;
    }

    const disabled = await disableTarget(targetId);
    await fetchTargets();
    return disabled;
  };

  return { targets, total, loading, error, refresh: fetchTargets, create: handleCreate, update: handleUpdate, disable: handleDisable };
}
