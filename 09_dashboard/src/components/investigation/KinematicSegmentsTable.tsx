import React from "react";
import { RouteSegment } from "../../types/api";
import { formatDistance, formatDuration, formatSpeed } from "../../utils/formatters";
import { FeasibilityBadge } from "../common/Badge";
import { ArrowRight, AlertTriangle } from "lucide-react";

interface KinematicSegmentsTableProps {
  segments: RouteSegment[];
}

export function KinematicSegmentsTable({ segments }: KinematicSegmentsTableProps) {
  if (segments.length === 0) {
    return null;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs font-mono">
        <thead className="bg-police-800/60 text-slate-400 uppercase text-[10px] border-b border-police-750">
          <tr>
            <th className="px-3 py-2">#</th>
            <th className="px-3 py-2">From Camera</th>
            <th className="px-3 py-2">To Camera</th>
            <th className="px-3 py-2">Time Delta</th>
            <th className="px-3 py-2">Lower-Bound Dist</th>
            <th className="px-3 py-2">Min Required Speed</th>
            <th className="px-3 py-2">Feasibility</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-police-800 text-slate-300">
          {segments.map((seg) => (
            <React.Fragment key={seg.segment_id}>
              <tr className="hover:bg-police-800/40 transition-colors">
                <td className="px-3 py-2.5 font-bold text-slate-400">{seg.sequence_index}</td>
                <td className="px-3 py-2.5 font-semibold text-slate-200">{seg.from_camera_id}</td>
                <td className="px-3 py-2.5 font-semibold text-slate-200">{seg.to_camera_id}</td>
                <td className="px-3 py-2.5">{formatDuration(seg.delta_seconds)}</td>
                <td className="px-3 py-2.5 font-semibold text-cyan-400">
                  {formatDistance(seg.distance_lower_bound_m)}
                </td>
                <td className="px-3 py-2.5 font-semibold text-slate-100">
                  {formatSpeed(seg.minimum_required_speed_kmh)}
                </td>
                <td className="px-3 py-2.5">
                  <FeasibilityBadge feasibility={seg.feasibility} />
                </td>
              </tr>
              {seg.warnings && seg.warnings.length > 0 && (
                <tr className="bg-amber-950/20 text-amber-300 text-[11px]">
                  <td colSpan={7} className="px-3 py-1.5 flex items-center gap-1.5 border-b border-police-800">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                    <span>{seg.warnings.join(" | ")}</span>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
