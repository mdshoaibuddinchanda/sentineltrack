import React from "react";
import { ReadinessMatrix } from "../components/system/ReadinessMatrix";
import { TelemetryGrid } from "../components/system/TelemetryGrid";
import { Card } from "../components/common/Card";
import { HealthResponse, ReadinessResponse, MetricsSnapshot } from "../types/api";
import { Server, Activity, ShieldAlert, CheckCircle, RefreshCw } from "lucide-react";

interface SystemPageProps {
  health?: HealthResponse | null;
  readiness?: ReadinessResponse | null;
  metrics?: MetricsSnapshot | null;
  lastUpdated?: Date | null;
  onRefresh: () => void;
}

export function SystemPage({
  health,
  readiness,
  metrics,
  lastUpdated,
  onRefresh,
}: SystemPageProps) {
  return (
    <div className="space-y-4">
      {/* Service Meta Card */}
      <Card
        title="SENTINELTRACK SYSTEM ARCHITECTURE & READINESS"
        subtitle="Central API gateway, PostgreSQL/PostGIS, and Computer Vision analytics engine"
        icon={<Server className="w-4 h-4 text-accent-blue" />}
        actions={
          <button
            onClick={onRefresh}
            className="flex items-center gap-1.5 px-3 py-1 bg-police-750 hover:bg-police-700 rounded text-xs font-mono font-semibold text-white transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> RE-PROBE
          </button>
        }
        bodyClassName="p-4"
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-xs">
          <div className="bg-police-900 p-3 rounded border border-police-800">
            <div className="text-slate-400 text-[11px]">SERVICE VERSION</div>
            <div className="text-sm font-bold text-slate-100">{health?.version || "1.0.0"}</div>
          </div>
          <div className="bg-police-900 p-3 rounded border border-police-800">
            <div className="text-slate-400 text-[11px]">GIT COMMIT SHA</div>
            <div className="text-xs font-bold text-cyan-300 truncate" title={health?.git_sha}>
              {health?.git_sha ? health.git_sha.substring(0, 8) : "21b9a1f0"}
            </div>
          </div>
          <div className="bg-police-900 p-3 rounded border border-police-800">
            <div className="text-slate-400 text-[11px]">SERVICE STATUS</div>
            <div className="text-sm font-bold text-emerald-400 uppercase">{health?.status || "HEALTHY"}</div>
          </div>
          <div className="bg-police-900 p-3 rounded border border-police-800">
            <div className="text-slate-400 text-[11px]">SECURITY / AUTH</div>
            <div className="text-xs font-bold text-amber-300">DEV MODE (P10 DEFERRED)</div>
          </div>
        </div>
      </Card>

      {/* Subsystem Readiness Matrix */}
      <Card
        title="SUBSYSTEM & MODEL READINESS MATRIX"
        subtitle="Individual health status of databases and computer vision inference pipelines"
        icon={<Activity className="w-4 h-4 text-cyan-400" />}
        bodyClassName="p-4"
      >
        <ReadinessMatrix readiness={readiness} />
      </Card>

      {/* Live Operational Telemetry */}
      <Card
        title="SESSION OPERATIONAL TELEMETRY SNAPSHOT"
        subtitle="Live metrics aggregated by backend MetricsCollector"
        icon={<Activity className="w-4 h-4 text-emerald-400" />}
        bodyClassName="p-4"
      >
        <TelemetryGrid metrics={metrics} />
      </Card>
    </div>
  );
}
