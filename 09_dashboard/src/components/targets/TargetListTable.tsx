import React from "react";
import { Target } from "../../types/api";
import { formatDateTime, maskRegistration } from "../../utils/formatters";
import { PriorityBadge } from "../common/Badge";
import { Compass, Edit3, Trash2, CheckCircle2, XCircle } from "lucide-react";

interface TargetListTableProps {
  targets: Target[];
  onInvestigate: (registration: string) => void;
  onEdit?: (target: Target) => void;
  onDisable?: (targetId: string) => void;
  privacyMode?: boolean;
}

export function TargetListTable({
  targets,
  onInvestigate,
  onEdit,
  onDisable,
  privacyMode = false,
}: TargetListTableProps) {
  if (targets.length === 0) {
    return (
      <div className="p-8 text-center text-slate-500 font-mono text-xs">
        No active targets registered on watchlist.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs font-mono">
        <thead className="bg-police-800/60 text-slate-400 uppercase text-[10px] border-b border-police-750">
          <tr>
            <th className="px-4 py-2.5">Target Registration</th>
            <th className="px-4 py-2.5">Priority</th>
            <th className="px-4 py-2.5">Status</th>
            <th className="px-4 py-2.5">Registered Time</th>
            <th className="px-4 py-2.5">Case / Notes</th>
            <th className="px-4 py-2.5 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-police-800 text-slate-300">
          {targets.map((t) => (
            <tr key={t.target_id} className="hover:bg-police-800/40 transition-colors">
              <td className="px-4 py-3">
                <div className="font-bold text-slate-100 text-sm">
                  {maskRegistration(t.registration, privacyMode)}
                </div>
                <div className="text-[10px] text-slate-500">
                  {maskRegistration(t.normalized_registration, privacyMode)}
                </div>
              </td>
              <td className="px-4 py-3">
                <PriorityBadge priority={t.priority} />
              </td>
              <td className="px-4 py-3">
                {t.enabled ? (
                  <span className="inline-flex items-center gap-1 text-emerald-400 text-xs">
                    <CheckCircle2 className="w-3.5 h-3.5" /> ACTIVE
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-slate-500 text-xs">
                    <XCircle className="w-3.5 h-3.5" /> DISABLED
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-slate-400">{formatDateTime(t.created_at)}</td>
              <td className="px-4 py-3 text-slate-300 max-w-xs truncate">
                {t.notes || t.metadata?.case_id || "--"}
              </td>
              <td className="px-4 py-3 text-right">
                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={() => onInvestigate(t.registration)}
                    title="Open GIS Trajectory Investigation"
                    className="p-1.5 bg-police-750 hover:bg-accent-blue/80 text-white rounded transition-colors"
                  >
                    <Compass className="w-3.5 h-3.5" />
                  </button>
                  {onEdit && (
                    <button
                      onClick={() => onEdit(t)}
                      title="Edit Target Entry"
                      className="p-1.5 bg-police-750 hover:bg-police-600 text-slate-300 hover:text-white rounded transition-colors"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {onDisable && t.enabled && (
                    <button
                      onClick={() => onDisable(t.target_id)}
                      title="Deactivate Target"
                      className="p-1.5 bg-police-750 hover:bg-rose-800/80 text-slate-400 hover:text-white rounded transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
