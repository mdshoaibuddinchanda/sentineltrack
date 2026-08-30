import React from "react";
import { MetricsSnapshot } from "../../types/api";
import { formatDuration } from "../../utils/formatters";
import { Activity, Cpu, Eye, Video, AlertOctagon, Compass, Radio } from "lucide-react";

export function TelemetryGrid({ metrics }: { metrics?: MetricsSnapshot | null }) {
  if (!metrics) {
    return <div className="p-4 text-xs font-mono text-slate-500">Live operational telemetry unavailable.</div>;
  }

  const items = [
    { label: "Requests handled", val: metrics.total_requests.toLocaleString(), icon: <Activity className="w-4 h-4 text-accent-blue" /> },
    { label: "Live update connections", val: metrics.active_ws_clients, icon: <Radio className="w-4 h-4 text-cyan-400" /> },
    { label: "Camera workers", val: metrics.active_camera_workers, icon: <Video className="w-4 h-4 text-emerald-400" /> },
    { label: "Frames received", val: metrics.total_frames_ingested.toLocaleString(), icon: <Cpu className="w-4 h-4 text-slate-300" /> },
    { label: "Vehicles found", val: metrics.total_vehicle_detections.toLocaleString(), icon: <Activity className="w-4 h-4 text-accent-blue" /> },
    { label: "Number plates found", val: metrics.total_plate_inferences.toLocaleString(), icon: <Eye className="w-4 h-4 text-amber-400" /> },
    { label: "Plate readings", val: metrics.total_ocr_inferences.toLocaleString(), icon: <Eye className="w-4 h-4 text-cyan-400" /> },
    { label: "Sightings saved", val: metrics.total_sightings_persisted.toLocaleString(), icon: <Eye className="w-4 h-4 text-emerald-400" /> },
    { label: "Alerts created", val: metrics.total_alerts_generated.toLocaleString(), icon: <AlertOctagon className="w-4 h-4 text-rose-400" /> },
    { label: "Route checks", val: metrics.total_routes_generated.toLocaleString(), icon: <Compass className="w-4 h-4 text-cyan-400" /> },
    { label: "Service uptime", val: formatDuration(metrics.uptime_seconds), icon: <Activity className="w-4 h-4 text-emerald-400" /> },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 font-mono text-xs select-none">
      {items.map((item, idx) => (
        <div key={idx} className="bg-police-850 border border-police-750 p-3 rounded-lg space-y-1">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
            {item.icon} {item.label}
          </div>
          <div className="text-lg font-bold text-slate-100">{item.val}</div>
        </div>
      ))}
    </div>
  );
}
