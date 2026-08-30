import React from "react";
import { ReadinessResponse } from "../../types/api";
import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";

export function ReadinessMatrix({ readiness }: { readiness?: ReadinessResponse | null }) {
  if (!readiness) {
    return <div className="p-4 text-xs font-mono text-slate-500">Readiness telemetry unavailable.</div>;
  }

  const components = [
    ...(readiness.components?.stream_ingestion !== undefined
      ? [{ key: "stream_ingestion", label: "Live camera feeds", desc: "Receives frames from the configured camera sources" }]
      : []),
    { key: "database", label: "Main database", desc: "Stores cameras, sightings, and watchlist data" },
    { key: "postgis", label: "Map and location service", desc: "Supports camera locations and route checks" },
    { key: "camera_registry", label: "Camera list", desc: "Camera addresses and connection details" },
    { key: "target_repository", label: "Watchlist storage", desc: "Vehicles and alert priorities" },
    { key: "route_engine", label: "Movement and route checks", desc: "Checks whether sightings can follow in time" },
    { key: "vehicle_detector", label: "Vehicle detection", desc: "Finds vehicles in incoming frames" },
    { key: "tracker", label: "Vehicle tracking", desc: "Follows vehicles across nearby frames" },
    { key: "plate_detector", label: "Number plate detection", desc: "Finds the plate area on a vehicle" },
    { key: "ocr_pipeline", label: "Number plate reading", desc: "Reads and checks plate text" },
    { key: "target_pipeline", label: "Watchlist matching and alerts", desc: "Compares sightings with the watchlist" },
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
            className={`operator-readiness operator-readiness--${isReady ? "ready" : isOffline ? "offline" : "unknown"} p-3 flex items-center justify-between gap-3`}
          >
            <div>
              <div className="operator-readiness__title">{comp.label}</div>
              <div className="operator-readiness__description text-[11px]">{comp.desc}</div>
            </div>

            <div className="shrink-0">
              {isReady && (
                <span className="operator-status operator-status--ready inline-flex items-center gap-1 text-xs">
                  <CheckCircle2 className="w-4 h-4" /> READY
                </span>
              )}
              {isOffline && (
                <span className="operator-status operator-status--offline inline-flex items-center gap-1 text-xs">
                  <XCircle className="w-4 h-4" /> OFFLINE
                </span>
              )}
              {isUnknown && (
                <span className="operator-status operator-status--unknown inline-flex items-center gap-1 text-xs">
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
