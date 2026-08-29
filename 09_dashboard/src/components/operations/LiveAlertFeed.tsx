import React from "react";
import { Alert } from "../../types/api";
import { formatRelativeTime, formatScore, maskRegistration } from "../../utils/formatters";
import { SeverityBadge, MatchClassBadge } from "../common/Badge";
import { AlertOctagon, Check, Compass } from "lucide-react";

interface LiveAlertFeedProps {
  alerts: Alert[];
  onAcknowledge: (alertId: string) => void;
  onInvestigate: (registration: string) => void;
  onSelectAlert?: (alert: Alert) => void;
  privacyMode?: boolean;
}

export function LiveAlertFeed({
  alerts,
  onAcknowledge,
  onInvestigate,
  onSelectAlert,
  privacyMode = false,
}: LiveAlertFeedProps) {
  if (alerts.length === 0) {
    return (
      <div className="p-8 text-center text-slate-400 font-mono text-xs flex flex-col items-center justify-center space-y-2">
        <Check className="w-8 h-8 text-emerald-500/60" />
        <p className="text-slate-300 font-semibold">No active unacknowledged alerts</p>
        <p className="text-[11px] text-slate-500">Real-time target watchlist detections will appear here automatically.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2.5 overflow-y-auto max-h-[460px] pr-1">
      {alerts.map((alert) => (
        <div
          key={alert.alert_id}
          onClick={() => onSelectAlert?.(alert)}
          className={`p-3 rounded-lg border transition-all ${
            alert.acknowledged
              ? "bg-police-850/60 border-police-750/60 opacity-75"
              : alert.severity === "CRITICAL"
              ? "bg-rose-950/30 border-rose-700/80 shadow-md shadow-rose-950/20"
              : "bg-police-850 border-police-750"
          } ${onSelectAlert ? "cursor-pointer" : ""}`}
        >
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex items-center gap-2 flex-wrap">
              {alert.severity === "CRITICAL" && <AlertOctagon className="w-4 h-4 text-rose-400" aria-label="Critical alert" />}
              <span className="text-sm font-bold text-slate-100 font-mono">
                {maskRegistration(alert.registration, privacyMode)}
              </span>
              <SeverityBadge severity={alert.severity} />
              <MatchClassBadge matchClass={alert.match_class} />
            </div>
            <span className="text-[11px] text-slate-400 font-mono shrink-0">
              {formatRelativeTime(alert.created_at)}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono text-slate-300 mb-3 bg-police-900/60 p-2 rounded border border-police-800">
            <div>
              <span className="text-slate-500">Camera: </span>
              <span className="text-slate-200 font-semibold">{alert.camera_id}</span>
            </div>
            <div>
              <span className="text-slate-500">Match Score: </span>
              <span className="text-cyan-400 font-semibold">{formatScore(alert.match_score)}</span>
            </div>
          </div>

          {alert.explanation && alert.explanation.length > 0 && (
            <p className="text-[11px] text-slate-400 italic line-clamp-1 mb-2.5">
              "{alert.explanation[0]}"
            </p>
          )}

          <div className="flex items-center justify-between gap-2 pt-2 border-t border-police-800/80">
            <button
              onClick={(event) => {
                event.stopPropagation();
                onInvestigate(alert.registration);
              }}
              className="flex items-center gap-1 px-2.5 py-1 bg-police-700 hover:bg-accent-blue/80 text-white rounded text-xs font-semibold font-mono transition-colors"
            >
              <Compass className="w-3.5 h-3.5" /> Trace Trajectory
            </button>

            {!alert.acknowledged ? (
              <button
                onClick={(event) => {
                  event.stopPropagation();
                  onAcknowledge(alert.alert_id);
                }}
                className="flex items-center gap-1 px-2.5 py-1 bg-emerald-800/80 hover:bg-emerald-700 text-white rounded text-xs font-semibold font-mono transition-colors"
              >
                <Check className="w-3.5 h-3.5" /> Acknowledge
              </button>
            ) : (
              <span className="text-[11px] text-emerald-400 font-mono flex items-center gap-1">
                <Check className="w-3.5 h-3.5" /> Ack by {alert.acknowledged_by || "operator"}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
