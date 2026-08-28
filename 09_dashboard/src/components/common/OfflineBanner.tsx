import React from "react";
import { AlertTriangle, WifiOff, RefreshCw } from "lucide-react";
import { SystemStatusType } from "../../hooks/useSystemStatus";

interface OfflineBannerProps {
  status: SystemStatusType;
  error?: string | null;
  onRetry: () => void;
  degradedDetails?: Record<string, any>;
}

export function OfflineBanner({ status, error, onRetry, degradedDetails }: OfflineBannerProps) {
  if (status === "HEALTHY" || status === "LOADING") return null;

  if (status === "OFFLINE") {
    return (
      <div className="bg-rose-950/90 border-b border-rose-700 text-rose-200 px-4 py-2 flex items-center justify-between text-xs sm:text-sm">
        <div className="flex items-center gap-2">
          <WifiOff className="w-4 h-4 text-rose-400 shrink-0" />
          <span className="font-semibold">SentinelTrack Backend Disconnected:</span>
          <span>{error || "Unable to reach FastAPI backend service (port 8000). Reconnecting automatically..."}</span>
        </div>
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-2.5 py-1 bg-rose-800/80 hover:bg-rose-700 rounded text-xs font-semibold text-white transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Re-Check
        </button>
      </div>
    );
  }

  if (status === "DEGRADED") {
    const failedMods = Object.entries(degradedDetails || {})
      .filter(([_, ready]) => ready === false)
      .map(([name]) => name);

    return (
      <div className="bg-amber-950/90 border-b border-amber-700 text-amber-200 px-4 py-2 flex items-center justify-between text-xs sm:text-sm">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span className="font-semibold">System Readiness Degraded:</span>
          <span>
            {failedMods.length > 0
              ? `Subsystems offline: ${failedMods.join(", ")}. Primary REST endpoints remain active.`
              : "One or more analytics modules report degraded readiness. Control room operations remain active."}
          </span>
        </div>
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-800/80 hover:bg-amber-700 rounded text-xs font-semibold text-white transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Probe
        </button>
      </div>
    );
  }

  return null;
}
