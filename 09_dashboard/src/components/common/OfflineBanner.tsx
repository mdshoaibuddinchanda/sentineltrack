import React from "react";
import { AlertTriangle, RefreshCw, WifiOff } from "lucide-react";
import { SystemStatusType } from "../../hooks/useSystemStatus";

interface OfflineBannerProps {
  status: SystemStatusType;
  error?: string | null;
  onRetry: () => void;
  degradedDetails?: Record<string, any>;
  liveInputAvailable?: boolean;
}

function readableName(name: string): string {
  if (name === "stream_ingestion") return "Live camera input";
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function OfflineBanner({ status, error, onRetry, degradedDetails, liveInputAvailable }: OfflineBannerProps) {
  if (status === "LOADING") return null;
  if (status === "HEALTHY" && liveInputAvailable !== false) return null;

  if (status === "OFFLINE") {
    return (
      <div className="connection-banner connection-banner--offline" role="status">
        <div className="connection-banner__message">
          <WifiOff size={19} aria-hidden="true" />
          <div>
            <strong>Connection lost</strong>
            <span>{error || "The SentinelTrack service is not responding. Information may be out of date."}</span>
          </div>
        </div>
        <button type="button" onClick={onRetry} className="connection-banner__button">
          <RefreshCw size={16} /> Check again
        </button>
      </div>
    );
  }

  const failedModules = Object.entries(degradedDetails || {})
    .filter(([, ready]) => ready === false)
    .filter(([name]) => name !== "stream_ingestion")
    .map(([name]) => readableName(name));

  const cameraInputUnavailable = status === "HEALTHY" && liveInputAvailable === false;

  return (
    <div className="connection-banner connection-banner--warning" role="status">
      <div className="connection-banner__message">
        <AlertTriangle size={19} aria-hidden="true" />
          <div>
            <strong>{cameraInputUnavailable ? "Camera input not connected" : "Some services need attention"}</strong>
            <span>
            {cameraInputUnavailable
              ? "The application is connected, but no camera source is currently delivering frames. This page checks again automatically."
              : failedModules.length > 0
              ? `${failedModules.join(", ")} unavailable. Core information remains available where possible.`
              : "The system is available with limited services."}
          </span>
        </div>
      </div>
      {!cameraInputUnavailable && (
        <button type="button" onClick={onRetry} className="connection-banner__button">
          <RefreshCw size={16} /> Check again
        </button>
      )}
    </div>
  );
}
