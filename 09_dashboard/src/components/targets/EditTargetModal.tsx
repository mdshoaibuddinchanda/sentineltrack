import React, { useState, useEffect } from "react";
import { Target, TargetPriority, TargetUpdateRequest } from "../../types/api";
import { maskRegistration } from "../../utils/formatters";
import { X, Shield, AlertTriangle, Check, Loader2 } from "lucide-react";

interface EditTargetModalProps {
  isOpen: boolean;
  onClose: () => void;
  target: Target | null;
  onSubmit: (targetId: string, data: TargetUpdateRequest) => Promise<any>;
  privacyMode?: boolean;
}

export function EditTargetModal({
  isOpen,
  onClose,
  target,
  onSubmit,
  privacyMode = false,
}: EditTargetModalProps) {
  const [priority, setPriority] = useState<TargetPriority>("NORMAL");
  const [enabled, setEnabled] = useState(true);
  const [notes, setNotes] = useState("");
  const [caseId, setCaseId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (target) {
      setPriority(target.priority || "NORMAL");
      setEnabled(target.enabled !== false);
      setNotes(target.notes || "");
      setCaseId(target.metadata?.case_id || "");
      setError(null);
    }
  }, [target]);

  if (!isOpen || !target) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const updateData: TargetUpdateRequest = {
        priority,
        enabled,
        notes: notes.trim() || undefined,
        metadata: {
          ...(target.metadata || {}),
          ...(caseId.trim() ? { case_id: caseId.trim() } : {}),
        },
      };

      await onSubmit(target.target_id, updateData);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to update target watchlist entry.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 select-none">
      <div className="bg-police-850 border border-police-750 rounded-xl shadow-2xl w-full max-w-md overflow-hidden font-sans">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-police-750 bg-police-800/60">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-accent-blue" />
            <h3 className="font-bold text-slate-100 text-sm font-mono tracking-wider">
              EDIT TARGET WATCHLIST ENTRY
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 transition-colors p-1 rounded hover:bg-police-750"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4 font-mono text-xs">
          {error && (
            <div className="p-3 bg-rose-950/40 border border-rose-600 rounded text-rose-200 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Registration (Immutable Identity) */}
          <div>
            <label className="block text-slate-400 uppercase text-[11px] font-bold mb-1">
              Target License Plate (Immutable)
            </label>
            <div className="w-full bg-police-900/80 border border-police-700 rounded px-3 py-2 text-slate-200 font-bold text-sm tracking-wider">
              {maskRegistration(target.registration, privacyMode)}
            </div>
          </div>

          {/* Priority */}
          <div>
            <label className="block text-slate-400 uppercase text-[11px] font-bold mb-1">
              Operational Priority Level
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as TargetPriority)}
              className="w-full bg-police-900 border border-police-700 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-accent-blue"
            >
              <option value="CRITICAL">CRITICAL — Armed / High Risk (Immediate Dispatch)</option>
              <option value="HIGH">HIGH — Stolen / Major Felony Investigation</option>
              <option value="NORMAL">NORMAL — Standard BOLO / Surveillance</option>
              <option value="LOW">LOW — Routine Traffic Infraction Check</option>
            </select>
          </div>

          {/* Enabled Status */}
          <div>
            <label className="flex items-center gap-2 cursor-pointer text-slate-300">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="rounded bg-police-900 border-police-700 text-accent-blue focus:ring-0"
              />
              <span className="font-bold text-xs">Active Watchlist Monitoring Enabled</span>
            </label>
          </div>

          {/* Case / FIR Reference */}
          <div>
            <label className="block text-slate-400 uppercase text-[11px] font-bold mb-1">
              Case / FIR Reference
            </label>
            <input
              type="text"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              placeholder="e.g. FIR-2026-SG-1092"
              className="w-full bg-police-900 border border-police-700 rounded px-3 py-2 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-accent-blue"
            />
          </div>

          {/* Notes */}
          <div>
            <label className="block text-slate-400 uppercase text-[11px] font-bold mb-1">
              Investigation Notes
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Operational notes, suspect details, vehicle make/model..."
              className="w-full bg-police-900 border border-police-700 rounded px-3 py-2 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-accent-blue resize-none"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-police-750">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-police-750 hover:bg-police-700 text-slate-300 rounded font-semibold transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-accent-blue hover:bg-blue-600 disabled:opacity-50 text-white rounded font-bold transition-colors flex items-center gap-1.5 shadow-lg shadow-accent-blue/20"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> SAVING...
                </>
              ) : (
                <>
                  <Check className="w-3.5 h-3.5" /> SAVE CHANGES
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
