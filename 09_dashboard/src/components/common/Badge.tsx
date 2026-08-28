import React from "react";
import { AlertSeverity, TargetPriority, FeasibilityClass, MatchClass, TimeQuality, CameraStreamStatus } from "../../types/api";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "critical" | "high" | "normal" | "low" | "success" | "warning" | "danger" | "neutral" | "cyan";
  size?: "sm" | "md" | "lg";
  className?: string;
  dot?: boolean;
}

export function Badge({ children, variant = "default", size = "md", className = "", dot = false }: BadgeProps) {
  const sizeClasses = {
    sm: "px-1.5 py-0.5 text-xs",
    md: "px-2.5 py-0.5 text-xs font-semibold tracking-wide",
    lg: "px-3 py-1 text-sm font-semibold",
  };

  const variantClasses = {
    default: "bg-police-700/60 text-slate-300 border border-police-600",
    critical: "bg-rose-950/80 text-rose-300 border border-rose-600/60",
    high: "bg-amber-950/80 text-amber-300 border border-amber-600/60",
    normal: "bg-blue-950/80 text-blue-300 border border-blue-600/60",
    low: "bg-slate-800 text-slate-400 border border-slate-700",
    success: "bg-emerald-950/80 text-emerald-300 border border-emerald-600/60",
    warning: "bg-amber-950/80 text-amber-300 border border-amber-600/60",
    danger: "bg-rose-950/80 text-rose-300 border border-rose-600/60",
    neutral: "bg-police-800 text-slate-400 border border-police-700",
    cyan: "bg-cyan-950/80 text-cyan-300 border border-cyan-600/60",
  };

  const dotClasses = {
    default: "bg-slate-400",
    critical: "bg-rose-500 animate-ping-slow",
    high: "bg-amber-500",
    normal: "bg-blue-500",
    low: "bg-slate-500",
    success: "bg-emerald-500",
    warning: "bg-amber-500",
    danger: "bg-rose-500",
    neutral: "bg-slate-500",
    cyan: "bg-cyan-500",
  };

  return (
    <span className={`inline-flex items-center gap-1.5 rounded uppercase font-mono ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}>
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dotClasses[variant]}`} />}
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  const map: Record<AlertSeverity, { variant: "critical" | "high" | "normal" | "low"; label: string }> = {
    CRITICAL: { variant: "critical", label: "CRITICAL" },
    HIGH: { variant: "high", label: "HIGH" },
    NORMAL: { variant: "normal", label: "NORMAL" },
    LOW: { variant: "low", label: "LOW" },
  };
  const conf = map[severity] || { variant: "low", label: severity };
  return <Badge variant={conf.variant} dot={severity === "CRITICAL"}>{conf.label}</Badge>;
}

export function PriorityBadge({ priority }: { priority: TargetPriority }) {
  const map: Record<TargetPriority, { variant: "critical" | "high" | "normal" | "low"; label: string }> = {
    CRITICAL: { variant: "critical", label: "CRITICAL" },
    HIGH: { variant: "high", label: "HIGH" },
    NORMAL: { variant: "normal", label: "NORMAL" },
    LOW: { variant: "low", label: "LOW" },
  };
  const conf = map[priority] || { variant: "low", label: priority };
  return <Badge variant={conf.variant}>{conf.label}</Badge>;
}

export function FeasibilityBadge({ feasibility }: { feasibility: FeasibilityClass }) {
  const map: Record<FeasibilityClass, { variant: "success" | "warning" | "danger" | "neutral"; label: string }> = {
    FEASIBLE: { variant: "success", label: "FEASIBLE" },
    QUESTIONABLE: { variant: "warning", label: "QUESTIONABLE" },
    IMPOSSIBLE: { variant: "danger", label: "IMPOSSIBLE SPEED" },
    UNKNOWN: { variant: "neutral", label: "UNKNOWN" },
  };
  const conf = map[feasibility] || { variant: "neutral", label: feasibility };
  return <Badge variant={conf.variant}>{conf.label}</Badge>;
}

export function MatchClassBadge({ matchClass }: { matchClass: MatchClass }) {
  const map: Record<MatchClass, { variant: "cyan" | "success" | "normal" | "neutral"; label: string }> = {
    EXACT: { variant: "cyan", label: "EXACT MATCH" },
    HIGH_PROBABILITY: { variant: "success", label: "HIGH PROBABILITY" },
    PROBABLE: { variant: "normal", label: "PROBABLE" },
    POSSIBLE: { variant: "neutral", label: "POSSIBLE" },
  };
  const conf = map[matchClass] || { variant: "neutral", label: matchClass };
  return <Badge variant={conf.variant}>{conf.label}</Badge>;
}

export function TimeQualityBadge({ quality }: { quality?: TimeQuality }) {
  if (!quality) return null;
  const map: Record<TimeQuality, { variant: "success" | "warning" | "danger" | "neutral"; label: string; tooltip: string }> = {
    HIGH: { variant: "success", label: "TIME: HIGH", tooltip: "Trusted source wall-clock timestamp" },
    MEDIUM: { variant: "warning", label: "TIME: MED", tooltip: "Monotonic PTS-anchored clock estimate" },
    LOW: { variant: "danger", label: "TIME: LOW", tooltip: "Database/Ingest fallback estimate" },
    UNKNOWN: { variant: "neutral", label: "TIME: UNK", tooltip: "Unknown clock source" },
  };
  const conf = map[quality] || { variant: "neutral", label: `TIME: ${quality}`, tooltip: "" };
  return (
    <span title={conf.tooltip}>
      <Badge variant={conf.variant} size="sm">{conf.label}</Badge>
    </span>
  );
}

export function CameraStatusBadge({ status }: { status: CameraStreamStatus }) {
  const map: Record<CameraStreamStatus, { variant: "success" | "warning" | "danger" | "neutral"; label: string }> = {
    ONLINE: { variant: "success", label: "ONLINE" },
    DEGRADED: { variant: "warning", label: "DEGRADED" },
    OFFLINE: { variant: "danger", label: "OFFLINE" },
    UNKNOWN: { variant: "neutral", label: "UNKNOWN" },
  };
  const conf = map[status] || { variant: "neutral", label: status };
  return <Badge variant={conf.variant} dot={status === "ONLINE"}>{conf.label}</Badge>;
}
