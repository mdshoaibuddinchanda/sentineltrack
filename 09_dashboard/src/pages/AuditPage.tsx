import React, { useState, useEffect, useCallback } from "react";
import { AuditEventItem, listAuditEvents } from "../api/audit";
import { ShieldCheck, Filter, RefreshCw, AlertTriangle, CheckCircle, XCircle, FileText } from "lucide-react";
import { formatUtcTime } from "../utils/formatters";

export function AuditPage() {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [filterAction, setFilterAction] = useState<string>("");
  const [filterOutcome, setFilterOutcome] = useState<string>("");
  const [filterUsername, setFilterUsername] = useState<string>("");
  const [selectedEvent, setSelectedEvent] = useState<AuditEventItem | null>(null);

  const fetchAudit = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listAuditEvents({
        action: filterAction || undefined,
        outcome: filterOutcome || undefined,
        actor_username: filterUsername || undefined,
        limit: 100,
      });
      setEvents(res.items);
      setTotal(res.total);
    } catch (err: any) {
      setError(err.message || "Failed to load audit trail.");
    } finally {
      setLoading(false);
    }
  }, [filterAction, filterOutcome, filterUsername]);

  useEffect(() => {
    fetchAudit();
  }, [fetchAudit]);

  const getOutcomeBadge = (outcome: string) => {
    switch (outcome.toUpperCase()) {
      case "SUCCESS":
        return (
          <span className="inline-flex items-center gap-1 text-emerald-400 text-xs font-semibold">
            <CheckCircle className="w-3.5 h-3.5" /> SUCCESS
          </span>
        );
      case "FAILURE":
        return (
          <span className="inline-flex items-center gap-1 text-rose-400 text-xs font-semibold">
            <XCircle className="w-3.5 h-3.5" /> FAILURE
          </span>
        );
      case "DENIED":
      case "BLOCKED":
        return (
          <span className="inline-flex items-center gap-1 text-amber-400 text-xs font-semibold">
            <AlertTriangle className="w-3.5 h-3.5" /> DENIED
          </span>
        );
      default:
        return <span className="text-slate-400 text-xs">{outcome}</span>;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-police-850 p-4 rounded-lg border border-police-750">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/40 text-emerald-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-wide text-white font-mono">SECURITY AUDIT TRAIL</h1>
            <p className="text-xs text-slate-400">Immutable, chronological record of operator authentication and operational actions</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchAudit}
            disabled={loading}
            className="p-2 rounded bg-police-800 hover:bg-police-700 border border-police-700 text-slate-300 transition-colors"
            title="Refresh Audit Log"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="bg-police-850 p-3 rounded-lg border border-police-750 flex flex-wrap items-center gap-3 text-xs font-mono">
        <div className="flex items-center gap-1.5 text-slate-400">
          <Filter className="w-4 h-4 text-accent-blue" />
          <span>FILTER:</span>
        </div>

        <div>
          <input
            type="text"
            value={filterUsername}
            onChange={(e) => setFilterUsername(e.target.value)}
            placeholder="Filter by operator username..."
            className="bg-police-900 border border-police-700 rounded px-2.5 py-1 text-slate-200 focus:outline-hidden text-xs"
          />
        </div>

        <div>
          <select
            value={filterAction}
            onChange={(e) => setFilterAction(e.target.value)}
            className="bg-police-900 border border-police-700 rounded px-2.5 py-1 text-slate-200 cursor-pointer focus:outline-hidden"
          >
            <option value="">All Actions</option>
            <option value="LOGIN_SUCCESS">LOGIN_SUCCESS</option>
            <option value="LOGIN_FAILURE">LOGIN_FAILURE</option>
            <option value="LOGOUT">LOGOUT</option>
            <option value="USER_CREATED">USER_CREATED</option>
            <option value="USER_UPDATED">USER_UPDATED</option>
            <option value="PASSWORD_CHANGED">PASSWORD_CHANGED</option>
            <option value="CREATE_TARGET">CREATE_TARGET</option>
            <option value="UPDATE_TARGET">UPDATE_TARGET</option>
            <option value="DISABLE_TARGET">DISABLE_TARGET</option>
            <option value="ACK_ALERT">ACK_ALERT</option>
            <option value="QUERY_ROUTE">QUERY_ROUTE</option>
          </select>
        </div>

        <div>
          <select
            value={filterOutcome}
            onChange={(e) => setFilterOutcome(e.target.value)}
            className="bg-police-900 border border-police-700 rounded px-2.5 py-1 text-slate-200 cursor-pointer focus:outline-hidden"
          >
            <option value="">All Outcomes</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="FAILURE">FAILURE</option>
            <option value="DENIED">DENIED</option>
          </select>
        </div>

        <div className="text-slate-400 ml-auto">
          Showing {events.length} of {total} logged events
        </div>
      </div>

      {error && (
        <div className="p-3 bg-rose-950/80 border border-rose-700 rounded-lg text-xs text-rose-200 flex items-center gap-2 font-mono">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Audit Table */}
      <div className="bg-police-850 rounded-lg border border-police-750 overflow-hidden shadow-lg">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-police-800/60 text-slate-400 border-b border-police-750">
              <tr>
                <th className="p-3">TIMESTAMP (UTC)</th>
                <th className="p-3">ACTION</th>
                <th className="p-3">OUTCOME</th>
                <th className="p-3">ACTOR</th>
                <th className="p-3">RESOURCE</th>
                <th className="p-3">SOURCE IP</th>
                <th className="p-3 text-right">DETAILS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-police-750/60 text-slate-200">
              {events.map((ev) => (
                <tr key={ev.audit_id} className="hover:bg-police-800/30 transition-colors">
                  <td className="p-3 text-slate-400 text-[11px]">
                    {formatUtcTime(ev.event_time_utc)}
                  </td>
                  <td className="p-3 font-semibold text-cyan-300">{ev.action}</td>
                  <td className="p-3">{getOutcomeBadge(ev.outcome)}</td>
                  <td className="p-3">
                    {ev.actor_username ? (
                      <span className="text-slate-200">
                        {ev.actor_username} <span className="text-[10px] text-slate-500">({ev.actor_role})</span>
                      </span>
                    ) : (
                      <span className="text-slate-500 italic">anonymous</span>
                    )}
                  </td>
                  <td className="p-3 text-slate-300">
                    {ev.resource_type} {ev.resource_id ? <span className="text-cyan-400 font-bold">[{ev.resource_id}]</span> : ""}
                  </td>
                  <td className="p-3 text-slate-400 text-[11px]">{ev.source_ip || "—"}</td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => setSelectedEvent(ev)}
                      className="px-2 py-1 rounded bg-police-800 hover:bg-police-700 border border-police-700 text-slate-300 hover:text-white inline-flex items-center gap-1 text-[11px]"
                    >
                      <FileText className="w-3 h-3 text-accent-blue" />
                      <span>View</span>
                    </button>
                  </td>
                </tr>
              ))}
              {events.length === 0 && !loading && (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-slate-500 font-mono">
                    No security events recorded matching the selected filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Event Details Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-police-850 border border-police-700 rounded-lg max-w-lg w-full p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-police-750 pb-3">
              <div className="flex items-center gap-2 text-white font-mono font-bold text-sm">
                <FileText className="w-4 h-4 text-accent-blue" />
                <span>AUDIT EVENT: {selectedEvent.audit_id}</span>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-slate-400 hover:text-white font-mono text-sm"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2 font-mono text-xs text-slate-300">
              <div><span className="text-slate-500">Timestamp (UTC):</span> {selectedEvent.event_time_utc}</div>
              <div><span className="text-slate-500">Action:</span> <span className="text-cyan-300 font-bold">{selectedEvent.action}</span></div>
              <div><span className="text-slate-500">Outcome:</span> {selectedEvent.outcome}</div>
              <div><span className="text-slate-500">Actor:</span> {selectedEvent.actor_username || "anonymous"} ({selectedEvent.actor_role || "none"})</div>
              <div><span className="text-slate-500">Resource:</span> {selectedEvent.resource_type} {selectedEvent.resource_id}</div>
              <div><span className="text-slate-500">Source IP:</span> {selectedEvent.source_ip || "N/A"}</div>
              <div><span className="text-slate-500">Request ID:</span> {selectedEvent.request_id || "N/A"}</div>
              <div><span className="text-slate-500">User Agent:</span> {selectedEvent.user_agent || "N/A"}</div>
              
              <div>
                <span className="text-slate-500 block mb-1">Details Payload:</span>
                <pre className="p-3 bg-police-900 border border-police-750 rounded text-[11px] text-slate-200 overflow-x-auto">
                  {JSON.stringify(selectedEvent.details, null, 2) || "None"}
                </pre>
              </div>
            </div>

            <div className="flex justify-end pt-3 border-t border-police-750">
              <button
                onClick={() => setSelectedEvent(null)}
                className="px-3 py-1.5 rounded bg-police-800 hover:bg-police-700 border border-police-700 text-slate-300 font-mono text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
