import React, { useState } from "react";
import { Alert } from "../types/api";
import { Card } from "../components/common/Card";
import { SeverityBadge, MatchClassBadge } from "../components/common/Badge";
import { formatDateTime, formatRelativeTime, formatScore, maskRegistration } from "../utils/formatters";
import { Bell, Check, Compass, Search, Filter, Shield } from "lucide-react";

interface AlertsPageProps {
  alerts: Alert[];
  onAcknowledge: (alertId: string) => void;
  onInvestigate: (registration: string) => void;
  privacyMode?: boolean;
}

export function AlertsPage({ alerts, onAcknowledge, onInvestigate, privacyMode = false }: AlertsPageProps) {
  const [search, setSearch] = useState("");
  const [unackOnly, setUnackOnly] = useState(false);
  const [severityFilter, setSeverityFilter] = useState("ALL");

  const filteredAlerts = alerts.filter((a) => {
    const matchesSearch =
      a.registration.toLowerCase().includes(search.toLowerCase()) ||
      a.camera_id.toLowerCase().includes(search.toLowerCase());

    const matchesUnack = !unackOnly || !a.acknowledged;
    const matchesSeverity = severityFilter === "ALL" || a.severity === severityFilter;

    return matchesSearch && matchesUnack && matchesSeverity;
  });

  return (
    <div className="space-y-4">
      {/* Search & Filters */}
      <div className="flex items-center justify-between gap-4 flex-wrap bg-police-850 p-3 rounded-lg border border-police-750 font-mono text-xs">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search alerts by target plate or camera ID..."
            className="w-full bg-police-900 border border-police-700 rounded pl-9 pr-3 py-1.5 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-accent-blue"
          />
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={unackOnly}
              onChange={(e) => setUnackOnly(e.target.checked)}
              className="rounded bg-police-900 border-police-700 text-accent-blue focus:ring-0"
            />
            <span>Unacknowledged Only</span>
          </label>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-police-900 border border-police-700 rounded px-2.5 py-1 text-slate-200 focus:outline-none"
          >
            <option value="ALL">ALL SEVERITY ({alerts.length})</option>
            <option value="CRITICAL">CRITICAL ({alerts.filter((a) => a.severity === "CRITICAL").length})</option>
            <option value="HIGH">HIGH ({alerts.filter((a) => a.severity === "HIGH").length})</option>
            <option value="NORMAL">NORMAL ({alerts.filter((a) => a.severity === "NORMAL").length})</option>
            <option value="LOW">LOW ({alerts.filter((a) => a.severity === "LOW").length})</option>
          </select>
        </div>
      </div>

      {/* Alerts Table */}
      <Card
        title={`INCIDENT ALERT LOG (${filteredAlerts.length})`}
        subtitle="Idempotent match detections with explainable OCR evidence"
        icon={<Bell className="w-4 h-4 text-rose-500" />}
        bodyClassName="p-0 overflow-x-auto"
      >
        {filteredAlerts.length === 0 ? (
          <div className="p-12 text-center text-slate-500 font-mono text-xs">
            No incident alerts matching selected criteria.
          </div>
        ) : (
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-police-800/60 text-slate-400 uppercase text-[10px] border-b border-police-750">
              <tr>
                <th className="px-4 py-2.5">Severity</th>
                <th className="px-4 py-2.5">Target Plate</th>
                <th className="px-4 py-2.5">Camera Node</th>
                <th className="px-4 py-2.5">Match Score</th>
                <th className="px-4 py-2.5">Match Class</th>
                <th className="px-4 py-2.5">Incident Time (UTC)</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-police-800 text-slate-300">
              {filteredAlerts.map((alt) => (
                <tr
                  key={alt.alert_id}
                  className={`hover:bg-police-800/40 transition-colors ${
                    !alt.acknowledged && alt.severity === "CRITICAL" ? "bg-rose-950/20" : ""
                  }`}
                >
                  <td className="px-4 py-3">
                    <SeverityBadge severity={alt.severity} />
                  </td>
                  <td className="px-4 py-3 font-bold text-slate-100 text-sm">
                    {maskRegistration(alt.registration, privacyMode)}
                  </td>
                  <td className="px-4 py-3 text-slate-300 font-semibold">{alt.camera_id}</td>
                  <td className="px-4 py-3 font-bold text-cyan-400">{formatScore(alt.match_score)}</td>
                  <td className="px-4 py-3">
                    <MatchClassBadge matchClass={alt.match_class} />
                  </td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTime(alt.created_at)}</td>
                  <td className="px-4 py-3">
                    {alt.acknowledged ? (
                      <span className="text-[11px] text-emerald-400 flex items-center gap-1">
                        <Check className="w-3.5 h-3.5" /> Ack by {alt.acknowledged_by || "operator"}
                      </span>
                    ) : (
                      <span className="text-[11px] text-rose-400 font-bold uppercase animate-pulse">
                        PENDING ACK
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => onInvestigate(alt.registration)}
                        title="Trace Cross-Camera Trajectory"
                        className="px-2.5 py-1 bg-police-750 hover:bg-accent-blue/80 text-white rounded text-[11px] font-semibold transition-colors flex items-center gap-1"
                      >
                        <Compass className="w-3.5 h-3.5" /> Trace
                      </button>
                      {!alt.acknowledged && (
                        <button
                          onClick={() => onAcknowledge(alt.alert_id)}
                          className="px-2.5 py-1 bg-emerald-800/80 hover:bg-emerald-700 text-white rounded text-[11px] font-semibold transition-colors flex items-center gap-1"
                        >
                          <Check className="w-3.5 h-3.5" /> Ack
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
