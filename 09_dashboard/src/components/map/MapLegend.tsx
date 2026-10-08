import React from "react";

export function MapLegend() {
  return (
    <div className="absolute bottom-4 left-4 z-[1000] bg-police-850/95 border border-police-750/90 rounded-md p-2.5 shadow-xl backdrop-blur-sm text-[11px] font-mono space-y-1.5 pointer-events-auto max-w-[200px]">
      <div className="font-bold text-slate-300 uppercase tracking-wider text-[10px] pb-1 border-b border-police-700">
        GIS Legend
      </div>
      <div className="flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
        <span className="text-slate-300">Camera (Online)</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0" />
        <span className="text-slate-300">Camera (Degraded)</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shrink-0" />
        <span className="text-slate-300">Camera (Offline)</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-3.5 h-1.5 bg-cyan-400 shrink-0 rounded-sm" />
        <span className="text-slate-300">Feasible Trajectory</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-3.5 h-1.5 bg-rose-500 shrink-0 rounded-sm" />
        <span className="text-slate-300">Impossible Velocity</span>
      </div>
    </div>
  );
}
