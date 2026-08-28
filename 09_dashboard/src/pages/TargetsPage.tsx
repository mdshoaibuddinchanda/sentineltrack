import React, { useState } from "react";
import { Target, TargetCreateRequest, TargetUpdateRequest } from "../types/api";
import { Card } from "../components/common/Card";
import { TargetListTable } from "../components/targets/TargetListTable";
import { AddTargetModal } from "../components/targets/AddTargetModal";
import { EditTargetModal } from "../components/targets/EditTargetModal";
import { Plus, Search, Activity } from "lucide-react";
import { useAuth } from "../context/AuthContext";

interface TargetsPageProps {
  targets: Target[];
  onCreateTarget: (data: TargetCreateRequest) => Promise<any>;
  onUpdateTarget?: (targetId: string, data: TargetUpdateRequest) => Promise<any>;
  onDisableTarget?: (targetId: string) => Promise<any>;
  onInvestigate: (registration: string) => void;
  privacyMode?: boolean;
}

export function TargetsPage({
  targets,
  onCreateTarget,
  onUpdateTarget,
  onDisableTarget,
  onInvestigate,
  privacyMode = false,
}: TargetsPageProps) {
  const { hasPermission, user } = useAuth();
  const canCreate = hasPermission("target:create") || user?.role === "ADMIN" || user?.role === "SUPERVISOR";
  const canEdit = hasPermission("target:update") || user?.role === "ADMIN" || user?.role === "SUPERVISOR";
  const canDisable = hasPermission("target:disable") || user?.role === "ADMIN" || user?.role === "SUPERVISOR";

  const [search, setSearch] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("ALL");

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingTarget, setEditingTarget] = useState<Target | null>(null);

  const filteredTargets = targets.filter((t) => {
    const matchesSearch =
      t.registration.toLowerCase().includes(search.toLowerCase()) ||
      t.normalized_registration.toLowerCase().includes(search.toLowerCase()) ||
      (t.notes && t.notes.toLowerCase().includes(search.toLowerCase()));

    const matchesPriority = priorityFilter === "ALL" || t.priority === priorityFilter;
    return matchesSearch && matchesPriority;
  });

  return (
    <div className="space-y-4">
      {/* Top Header & Actions */}
      <div className="flex items-center justify-between gap-4 flex-wrap bg-police-850 p-3 rounded-lg border border-police-750 font-mono text-xs">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter target watchlists by plate, case ID, or notes..."
            className="w-full bg-police-900 border border-police-700 rounded pl-9 pr-3 py-1.5 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-accent-blue"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-400">PRIORITY:</span>
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="bg-police-900 border border-police-700 rounded px-2.5 py-1 text-slate-200 focus:outline-none"
          >
            <option value="ALL">ALL ({targets.length})</option>
            <option value="CRITICAL">CRITICAL ({targets.filter((t) => t.priority === "CRITICAL").length})</option>
            <option value="HIGH">HIGH ({targets.filter((t) => t.priority === "HIGH").length})</option>
            <option value="NORMAL">NORMAL ({targets.filter((t) => t.priority === "NORMAL").length})</option>
            <option value="LOW">LOW ({targets.filter((t) => t.priority === "LOW").length})</option>
          </select>
        </div>

        {canCreate && (
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-accent-blue hover:bg-blue-600 text-white rounded font-bold font-mono tracking-wider transition-colors shadow-lg shadow-accent-blue/20"
          >
            <Plus className="w-4 h-4" /> REGISTER TARGET
          </button>
        )}
      </div>

      {/* Target Watchlist Table */}
      <Card
        title={`ACTIVE TARGET WATCHLISTS (${filteredTargets.length})`}
        subtitle="Automatic plate matching & real-time alert trigger registry"
        icon={<Activity className="w-4 h-4 text-accent-blue" />}
        bodyClassName="p-0"
      >
        <TargetListTable
          targets={filteredTargets}
          onInvestigate={onInvestigate}
          onEdit={canEdit ? (t) => setEditingTarget(t) : undefined}
          onDisable={canDisable ? onDisableTarget : undefined}
          privacyMode={privacyMode}
        />
      </Card>


      {/* Add Target Modal */}
      <AddTargetModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSubmit={onCreateTarget}
      />

      {/* Edit Target Modal */}
      {editingTarget && (
        <EditTargetModal
          isOpen={Boolean(editingTarget)}
          onClose={() => setEditingTarget(null)}
          target={editingTarget}
          onSubmit={onUpdateTarget || (async () => {})}
          privacyMode={privacyMode}
        />
      )}
    </div>
  );
}
