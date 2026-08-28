import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Alert } from "../types/api";
import { Card } from "../components/common/Card";
import { SeverityBadge, MatchClassBadge } from "../components/common/Badge";
import { formatDateTime, formatScore, maskRegistration } from "../utils/formatters";
import { getAlert } from "../api/alerts";
import { Bell, Check, Compass, Search, Filter, X, Loader2, AlertCircle } from "lucide-react";
import { useAuth } from "../context/AuthContext";

interface AlertsPageProps {
  alerts: Alert[];
  onAcknowledge: (alertId: string) => void;
  onInvestigate: (registration: string) => void;
  privacyMode?: boolean;
}

export function AlertsPage({ alerts, onAcknowledge, onInvestigate, privacyMode = false }: AlertsPageProps) {
  const { hasPermission, user } = useAuth();
  const canAck = hasPermission("alert:ack") || user?.role === "ADMIN" || user?.role === "SUPERVISOR" || user?.role === "OPERATOR";
  const { alertId: routeAlertId } = useParams<{ alertId?: string }>();
  const navigate = useNavigate();


  const [search, setSearch] = useState("");
  const [unackOnly, setUnackOnly] = useState(false);
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [directAlert, setDirectAlert] = useState<Alert | null>(null);
  const [loadingDirectAlert, setLoadingDirectAlert] = useState(false);
  const [directAlertNotFound, setDirectAlertNotFound] = useState(false);

  // Authoritative fetch for routeAlertId if absent from preloaded list
  useEffect(() => {
    if (!routeAlertId) {
      setDirectAlert(null);
      setDirectAlertNotFound(false);
      setLoadingDirectAlert(false);
      return;
    }

    const cached = alerts.find((a) => a.alert_id === routeAlertId);
    if (cached) {
      setDirectAlert(cached);
      setDirectAlertNotFound(false);
      setLoadingDirectAlert(false);
      return;
    }

    // Not in current local state cache -> fetch authoritative record from PostgreSQL via P8 API
    let isCancelled = false;
    setLoadingDirectAlert(true);
    setDirectAlertNotFound(false);

    getAlert(routeAlertId)
      .then((fetched) => {
        if (!isCancelled) {
          setDirectAlert(fetched);
          setDirectAlertNotFound(false);
        }
      })
      .catch(() => {
        if (!isCancelled) {
          setDirectAlert(null);
          setDirectAlertNotFound(true);
        }
      })
      .finally(() => {
        if (!isCancelled) {
          setLoadingDirectAlert(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [routeAlertId, alerts]);

  // Combine loaded alerts and direct alert if fetched
  const combinedAlerts =
    directAlert && !alerts.some((a) => a.alert_id === directAlert.alert_id)
      ? [directAlert, ...alerts]
      : alerts;

  const filteredAlerts = combinedAlerts.filter((a) => {
    if (routeAlertId && a.alert_id !== routeAlertId) {
      return false;
    }
    const matchesSearch =
      a.registration.toLowerCase().includes(search.toLowerCase()) ||
      a.camera_id.toLowerCase().includes(search.toLowerCase());

    const matchesUnack = !unackOnly || !a.acknowledged;
    const matchesSeverity = severityFilter === "ALL" || a.severity === severityFilter;

    return matchesSearch && matchesUnack && matchesSeverity;
  });

  return (
    <div className="space-y-4">
      {/* Route Filter Focus Banner */}
      {routeAlertId && (
        <div className="bg-police-800 border border-cyan-500/60 p-3 rounded-lg flex items-center justify-between font-mono text-xs text-slate-200">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-cyan-400" />
            <span>
              Filtering by Alert ID: <strong className="text-white">{routeAlertId}</strong>
            </span>
            {loadingDirectAlert && (
              <span className="flex items-center gap-1 text-cyan-300 text-[11px] ml-2">
                <Loader2 className="w-3 h-3 animate-spin" /> Querying backend...
              </span>
            )}
          </div>
          <button
            onClick={() => navigate("/alerts")}
            className="flex items-center gap-1 px-2 py-0.5 bg-police-700 hover:bg-police-600 rounded text-slate-300 hover:text-white"
          >
            <X className="w-3.5 h-3.5" /> Show All Alerts
          </button>
        </div>
      )}

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
            <option value="ALL">ALL SEVERITY ({combinedAlerts.length})</option>
            <option value="CRITICAL">CRITICAL ({combinedAlerts.filter((a) => a.severity === "CRITICAL").length})</option>
            <option value="HIGH">HIGH ({combinedAlerts.filter((a) => a.severity === "HIGH").length})</option>
            <option value="NORMAL">NORMAL ({combinedAlerts.filter((a) => a.severity === "NORMAL").length})</option>
            <option value="LOW">LOW ({combinedAlerts.filter((a) => a.severity === "LOW").length})</option>
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
        {loadingDirectAlert ? (
          <div className="p-12 text-center text-slate-400 font-mono text-xs flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
            <span>Fetching authoritative alert record from database...</span>
          </div>
        ) : filteredAlerts.length === 0 ? (
          <div className="p-12 text-center text-slate-500 font-mono text-xs">
            {directAlertNotFound ? (
              <div className="flex items-center justify-center gap-2 text-amber-400">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>Alert '{routeAlertId}' not found in database.</span>
              </div>
            ) : routeAlertId ? (
              `Alert '${routeAlertId}' not found.`
            ) : (
              "No incident alerts matching selected criteria."
            )}
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
                  onClick={() => navigate(`/alerts/${encodeURIComponent(alt.alert_id)}`)}
                  className={`hover:bg-police-800/40 transition-colors cursor-pointer ${
                    !alt.acknowledged && alt.severity === "CRITICAL" ? "bg-rose-950/20" : ""
                  } ${routeAlertId === alt.alert_id ? "ring-1 ring-cyan-400 bg-police-800/80" : ""}`}
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
                    <div className="flex items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => onInvestigate(alt.registration)}
                        title="Trace Cross-Camera Trajectory"
                        className="px-2.5 py-1 bg-police-750 hover:bg-accent-blue/80 text-white rounded text-[11px] font-semibold transition-colors flex items-center gap-1"
                      >
                        <Compass className="w-3.5 h-3.5" /> Trace
                      </button>
                      {!alt.acknowledged && canAck && (
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
