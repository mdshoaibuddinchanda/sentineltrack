import React from "react";
import { AlertTriangle, CheckCircle, Info } from "lucide-react";

interface WarningsPanelProps {
  status: string;
  reasons?: string[];
  warnings?: string[];
}

export function WarningsPanel({ status, reasons = [], warnings = [] }: WarningsPanelProps) {
  if (reasons.length === 0 && warnings.length === 0 && status === "PLAUSIBLE_SEQUENCE") {
    return null;
  }

  return (
    <div className="space-y-3 select-none">
      {status === "CONFLICTING_SIGHTINGS" && (
        <div className="p-3.5 bg-rose-950/40 border border-rose-700/80 rounded-lg text-rose-200 text-xs font-mono space-y-1.5">
          <div className="flex items-center gap-2 font-bold text-rose-300">
            <AlertTriangle className="w-4 h-4 text-rose-400" /> PHYSICAL TRAJECTORY CONFLICT DETECTED
          </div>
          <p className="text-[11px] text-rose-300/80 leading-relaxed">
            Two high-confidence observations cannot be physically reconciled under kinematic speed constraints. Possible causes:
            camera clock skew, duplicate/cloned license plate, or incorrect camera geography.
          </p>
        </div>
      )}

      {status === "AMBIGUOUS" && (
        <div className="p-3.5 bg-amber-950/40 border border-amber-700/80 rounded-lg text-amber-200 text-xs font-mono space-y-1.5">
          <div className="flex items-center gap-2 font-bold text-amber-300">
            <Info className="w-4 h-4 text-amber-400" /> AMBIGUOUS TRAJECTORY CANDIDATES
          </div>
          <p className="text-[11px] text-amber-300/80 leading-relaxed">
            Multiple plausible trajectory sequences exist due to close temporal sightings across divergent corridors.
          </p>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="p-3 bg-police-850 border border-police-750 rounded-lg space-y-1.5">
          <div className="text-xs font-bold text-amber-400 font-mono flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" /> Trajectory Warnings
          </div>
          <ul className="space-y-1 text-xs text-slate-300 font-mono pl-4 list-disc">
            {warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {reasons.length > 0 && (
        <div className="p-3 bg-police-850 border border-police-750 rounded-lg space-y-1.5">
          <div className="text-xs font-bold text-emerald-400 font-mono flex items-center gap-1.5">
            <CheckCircle className="w-3.5 h-3.5" /> Trajectory Evidence Justification
          </div>
          <ul className="space-y-1 text-xs text-slate-300 font-mono pl-4 list-disc">
            {reasons.map((r, idx) => (
              <li key={idx}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
