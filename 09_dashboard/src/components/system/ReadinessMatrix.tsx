import React from "react";
import { ReadinessResponse } from "../../types/api";
import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";

export function ReadinessMatrix({ readiness }: { readiness?: ReadinessResponse | null }) {
  if (!readiness) {
    return <div className="p-4 text-xs font-mono text-slate-500">Readiness telemetry unavailable.</div>;
  }

  const components = [
    { key: "database", label: "PostgreSQL 17 Database", desc: "Relational persistence layer" },
    { key: "postgis", label: "PostGIS Spatial Engine", desc: "Geodesic ST_DWithin & GeoJSON" },
    { key: "camera_registry", label: "CCTV Camera Registry", desc: "Stream endpoints & hardware metadata" },
    { key: "target_repository", label: "Target Watchlist DB", desc: "Watchlist storage & fast indices" },
    { key: "route_engine", label: "P7 GIS Trajectory Pipeline", desc: "Kinematic feasibility & route DP" },
    { key: "vehicle_detector", label: "P1 Vehicle Detector (YOLO11m)", desc: "COCO vehicle detection & FP16 micro-batching" },
    { key: "tracker", label: "P2 Multi-Camera Tracker (ByteTrack)", desc: "Temporal vehicle association & track registry" },
    { key: "plate_detector", label: "P3 Plate Detector (YOLO11s)", desc: "License plate bounding box & quality score" },
    { key: "ocr_pipeline", label: "P4 OCR Recognizer (PP-OCRv5 ONNX)", desc: "Grammar scoring & multi-frame consensus" },
    { key: "target_pipeline", label: "P5 Target Matcher & Alert Engine", desc: "Position confusion discount & explainable scoring" },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 font-mono text-xs select-none">
      {components.map((comp) => {
        const val = readiness.components ? readiness.components[comp.key] : undefined;
        const isReady = val === true;
        const isOffline = val === false;
        const isUnknown = val === undefined;

        return (
          <div
            key={comp.key}
            className={`p-3 rounded-lg border flex items-center justify-between gap-3 ${
              isReady
                ? "bg-police-850 border-police-750"
                : isOffline
                ? "bg-rose-950/30 border-rose-700/80 text-rose-200"
                : "bg-amber-950/30 border-amber-700/80 text-amber-200"
            }`}
          >
            <div>
              <div className="font-semibold text-slate-100">{comp.label}</div>
              <div className="text-[11px] text-slate-400">{comp.desc}</div>
            </div>

            <div className="shrink-0">
              {isReady && (
                <span className="inline-flex items-center gap-1 text-emerald-400 font-bold text-xs">
                  <CheckCircle2 className="w-4 h-4" /> READY
                </span>
              )}
              {isOffline && (
                <span className="inline-flex items-center gap-1 text-rose-400 font-bold text-xs">
                  <XCircle className="w-4 h-4" /> OFFLINE
                </span>
              )}
              {isUnknown && (
                <span className="inline-flex items-center gap-1 text-amber-400 font-bold text-xs">
                  <AlertTriangle className="w-4 h-4" /> UNKNOWN
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
