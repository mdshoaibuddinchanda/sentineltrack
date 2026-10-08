import React from "react";
import { RouteResponse, RouteSummaryResponse } from "../../types/api";
import { formatDistance, formatDuration, formatScore, formatSpeed, maskRegistration } from "../../utils/formatters";

import { Badge } from "../common/Badge";
import { Clock, MapPin, Gauge, ShieldCheck } from "lucide-react";


interface TrajectorySummaryCardProps {
  route: RouteResponse;
  summary?: RouteSummaryResponse | null;
  privacyMode?: boolean;
}

export function TrajectorySummaryCard({ route, summary: _summary, privacyMode = false }: TrajectorySummaryCardProps) {
  const getStatusBadge = () => {
    switch (route.status) {
      case "CONFIRMED_SEQUENCE":
        return <Badge variant="success">CONFIRMED SEQUENCE</Badge>;
      case "PLAUSIBLE_SEQUENCE":
        return <Badge variant="success">PLAUSIBLE TRAJECTORY</Badge>;
      case "AMBIGUOUS":
        return <Badge variant="warning">AMBIGUOUS TRAJECTORY</Badge>;
      case "CONFLICTING_SIGHTINGS":
        return <Badge variant="danger">CONFLICTING SIGHTINGS</Badge>;
      case "SINGLE_SIGHTING":
        return <Badge variant="neutral">SINGLE SIGHTING ONLY</Badge>;
      case "INSUFFICIENT_EVIDENCE":
        return <Badge variant="warning">INSUFFICIENT EVIDENCE</Badge>;
      case "NO_ROUTE":
      default:
        return <Badge variant="neutral">NO ROUTE INFERRED</Badge>;
    }
  };

  return (
    <div className="bg-police-850 border border-police-750 p-4 rounded-lg space-y-4 shadow-xl select-none">
      <div className="flex items-start justify-between gap-4 flex-wrap pb-3 border-b border-police-750/80">
        <div>
          <div className="text-xs font-mono text-slate-400">INVESTIGATION TARGET</div>
          <div className="text-2xl font-bold font-mono text-slate-100 tracking-wider">
            {maskRegistration(route.registration, privacyMode)}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {getStatusBadge()}
          <div className="px-2.5 py-1 bg-police-800 border border-police-700 rounded text-xs font-mono">
            <span className="text-slate-400">Confidence: </span>
            <span className="font-bold text-cyan-400">{formatScore(route.trajectory_confidence)}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
        <div className="bg-police-900/60 p-2.5 rounded border border-police-800">
          <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
            <MapPin className="w-3.5 h-3.5 text-accent-blue" /> Lower-Bound Dist
          </div>
          <div className="text-base font-bold text-slate-100">
            {formatDistance(route.total_lower_bound_distance_m)}
          </div>
        </div>

        <div className="bg-police-900/60 p-2.5 rounded border border-police-800">
          <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
            <Clock className="w-3.5 h-3.5 text-cyan-400" /> Transit Duration
          </div>
          <div className="text-base font-bold text-slate-100">
            {formatDuration(route.duration_seconds)}
          </div>
        </div>

        <div className="bg-police-900/60 p-2.5 rounded border border-police-800">
          <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
            <Gauge className="w-3.5 h-3.5 text-emerald-400" /> Min Average Speed
          </div>
          <div className="text-base font-bold text-slate-100">
            {formatSpeed(route.minimum_average_speed_kmh)}
          </div>
        </div>

        <div className="bg-police-900/60 p-2.5 rounded border border-police-800">
          <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-amber-400" /> Sightings / Cams
          </div>
          <div className="text-base font-bold text-slate-100">
            {route.sighting_count} <span className="text-xs text-slate-500 font-normal">({route.camera_count} cams)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
