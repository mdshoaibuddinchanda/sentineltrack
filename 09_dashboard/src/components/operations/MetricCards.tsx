import React from "react";
import { Video, AlertOctagon, Activity, Eye, Cpu } from "lucide-react";

interface MetricCardsProps {
  onlineCameras: number;
  offlineCameras: number;
  totalCameras: number;
  activeTargets: number;
  unackAlerts: number;
  loadedSightingsCount: number;
  persistedSightingsTotal?: number;
  analyticsStatus: boolean;
  workerCount: number;
}

export function MetricCards({
  onlineCameras,
  offlineCameras,
  totalCameras,
  activeTargets,
  unackAlerts,
  loadedSightingsCount,
  persistedSightingsTotal,
  analyticsStatus,
  workerCount,
}: MetricCardsProps) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-6 gap-3 select-none">
      {/* Cameras Online */}
      <div className="bg-police-850 border border-police-750 p-3 rounded-lg flex items-center gap-3">
        <div className="p-2.5 rounded-md bg-emerald-950/80 border border-emerald-600/40 text-emerald-400">
          <Video className="w-5 h-5" />
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-mono uppercase">Cameras Online</div>
          <div className="text-xl font-bold text-slate-100 font-mono">
            {onlineCameras} <span className="text-xs text-slate-500 font-normal">/ {totalCameras}</span>
          </div>
        </div>
      </div>

      {/* Cameras Degraded / Offline */}
      <div className="bg-police-850 border border-police-750 p-3 rounded-lg flex items-center gap-3">
        <div className={`p-2.5 rounded-md border ${
          offlineCameras > 0 ? "bg-amber-950/80 border-amber-600/40 text-amber-400" : "bg-police-800 border-police-700 text-slate-500"
        }`}>
          <Video className="w-5 h-5" />
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-mono uppercase">Offline / Degraded</div>
          <div className="text-xl font-bold text-slate-100 font-mono">{offlineCameras}</div>
        </div>
      </div>

      {/* Active Targets */}
      <div className="bg-police-850 border border-police-750 p-3 rounded-lg flex items-center gap-3">
        <div className="p-2.5 rounded-md bg-blue-950/80 border border-blue-600/40 text-accent-blue">
          <Activity className="w-5 h-5" />
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-mono uppercase">Active Watchlist</div>
          <div className="text-xl font-bold text-slate-100 font-mono">{activeTargets}</div>
        </div>
      </div>

      {/* Unacknowledged Alerts */}
      <div className={`p-3 rounded-lg border flex items-center gap-3 ${
        unackAlerts > 0 ? "bg-rose-950/40 border-rose-700/80 shadow-lg shadow-rose-950/30" : "bg-police-850 border-police-750"
      }`}>
        <div className={`p-2.5 rounded-md border ${
          unackAlerts > 0 ? "bg-rose-950 border-rose-600 text-rose-400 animate-pulse" : "bg-police-800 border-police-700 text-slate-500"
        }`}>
          <AlertOctagon className="w-5 h-5" />
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-mono uppercase">Active Alerts</div>
          <div className="text-xl font-bold text-rose-300 font-mono">{unackAlerts}</div>
        </div>
      </div>

      {/* Sightings (Persisted & Loaded) */}
      <div className="bg-police-850 border border-police-750 p-3 rounded-lg flex items-center gap-3">
        <div className="p-2.5 rounded-md bg-cyan-950/80 border border-cyan-600/40 text-cyan-400">
          <Eye className="w-5 h-5" />
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-mono uppercase">Persisted Sightings</div>
          <div className="text-xl font-bold text-slate-100 font-mono">
            {persistedSightingsTotal !== undefined ? persistedSightingsTotal : loadedSightingsCount}{" "}
            <span className="text-[10px] text-slate-500 font-normal">({loadedSightingsCount} loaded)</span>
          </div>
        </div>
      </div>

      {/* Analytics Worker Status */}
      <div className="bg-police-850 border border-police-750 p-3 rounded-lg flex items-center gap-3">
        <div className={`p-2.5 rounded-md border ${
          analyticsStatus && workerCount > 0
            ? "bg-emerald-950/80 border-emerald-600/40 text-emerald-400"
            : "bg-police-800 border-police-700 text-slate-500"
        }`}>
          <Cpu className="w-5 h-5" />
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-mono uppercase">Analytics Engine</div>
          <div className="text-xs font-bold text-slate-100 font-mono">
            {!analyticsStatus
              ? "STOPPED"
              : workerCount > 0
              ? `${workerCount} Workers Active`
              : "0 Workers (IDLE)"}
          </div>
        </div>
      </div>
    </div>
  );
}
