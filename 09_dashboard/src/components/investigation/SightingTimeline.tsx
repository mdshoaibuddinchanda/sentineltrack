import React from "react";
import { RouteSighting, Sighting } from "../../types/api";
import { formatDateTime, formatScore, maskRegistration } from "../../utils/formatters";
import { TimeQualityBadge } from "../common/Badge";
import { MapPin, CheckCircle, Navigation } from "lucide-react";

interface SightingTimelineProps {
  sightings: RouteSighting[];
  selectedSightingId?: string | null;
  onSelectSighting: (sightingId: string) => void;
  privacyMode?: boolean;
}

export function SightingTimeline({
  sightings,
  selectedSightingId,
  onSelectSighting,
  privacyMode = false,
}: SightingTimelineProps) {
  if (sightings.length === 0) {
    return (
      <div className="p-6 text-center text-slate-500 font-mono text-xs">
        No sightings in chronological timeline.
      </div>
    );
  }

  return (
    <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-police-700">
      {sightings.map((s, idx) => {
        const isSelected = selectedSightingId === s.sighting_id;
        return (
          <div
            key={s.sighting_id}
            onClick={() => onSelectSighting(s.sighting_id)}
            className={`relative p-3 rounded-lg border cursor-pointer transition-all ${
              isSelected
                ? "bg-police-800 border-cyan-400 ring-2 ring-cyan-500/30 shadow-lg shadow-cyan-950/40"
                : "bg-police-850 border-police-750 hover:border-police-600 hover:bg-police-800/60"
            }`}
          >
            {/* Sequence Node Dot */}
            <div
              className={`absolute -left-[27px] top-3.5 w-5 h-5 rounded-full border-2 flex items-center justify-center text-[10px] font-mono font-bold transition-transform ${
                isSelected
                  ? "bg-cyan-500 border-white text-police-900 scale-125"
                  : "bg-police-900 border-cyan-400 text-cyan-300"
              }`}
            >
              {idx + 1}
            </div>

            <div className="flex items-start justify-between gap-2 mb-1.5">
              <div>
                <span className="text-xs font-bold text-slate-100 font-mono flex items-center gap-1">
                  <MapPin className="w-3 h-3 text-cyan-400 shrink-0" />
                  {s.camera_id}
                </span>
              </div>
              <TimeQualityBadge quality={s.time_quality} />
            </div>

            <div className="text-xs font-mono text-slate-300">{formatDateTime(s.event_time_utc)}</div>

            <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 mt-2 pt-2 border-t border-police-800">
              <span>Match Score:</span>
              <span className="text-cyan-400 font-bold">{formatScore(s.match_score)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
