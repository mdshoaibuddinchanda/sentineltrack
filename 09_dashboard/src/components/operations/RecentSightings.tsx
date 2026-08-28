import React from "react";
import { Sighting } from "../../types/api";
import { formatDateTime, formatScore, maskRegistration } from "../../utils/formatters";
import { MatchClassBadge, TimeQualityBadge } from "../common/Badge";
import { Eye, Compass } from "lucide-react";

interface RecentSightingsProps {
  sightings: Sighting[];
  onInvestigate: (registration: string) => void;
  privacyMode?: boolean;
}

export function RecentSightings({
  sightings,
  onInvestigate,
  privacyMode = false,
}: RecentSightingsProps) {
  if (sightings.length === 0) {
    return (
      <div className="p-6 text-center text-slate-500 font-mono text-xs">
        No recent vehicle sightings recorded.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs font-mono">
        <thead className="bg-police-800/60 text-slate-400 uppercase text-[10px] border-b border-police-750">
          <tr>
            <th className="px-3 py-2">Plate Candidate</th>
            <th className="px-3 py-2">Camera</th>
            <th className="px-3 py-2">Event Time (UTC)</th>
            <th className="px-3 py-2">Score</th>
            <th className="px-3 py-2">Class</th>
            <th className="px-3 py-2">Time Quality</th>
            <th className="px-3 py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-police-800 text-slate-300">
          {sightings.slice(0, 8).map((s) => (
            <tr key={s.sighting_id} className="hover:bg-police-800/40 transition-colors">
              <td className="px-3 py-2 font-bold text-slate-100">
                {maskRegistration(s.registration_candidate, privacyMode)}
              </td>
              <td className="px-3 py-2 text-slate-400">{s.camera_id}</td>
              <td className="px-3 py-2">{formatDateTime(s.event_time_utc || s.created_at)}</td>
              <td className="px-3 py-2 text-cyan-400 font-bold">{formatScore(s.match_score)}</td>
              <td className="px-3 py-2">
                <MatchClassBadge matchClass={s.match_class} />
              </td>
              <td className="px-3 py-2">
                <TimeQualityBadge quality={s.event_time_quality} />
              </td>
              <td className="px-3 py-2 text-right">
                <button
                  onClick={() => onInvestigate(s.registration_candidate)}
                  className="px-2 py-0.5 bg-police-750 hover:bg-accent-blue/80 text-white rounded text-[11px] font-semibold transition-colors"
                >
                  Investigate
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
