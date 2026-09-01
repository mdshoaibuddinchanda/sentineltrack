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
    <span className={`operator-badge operator-badge--${variant} inline-flex items-center gap-1.5 rounded uppercase font-mono ${sizeClasses[size]} ${className}`}>
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
    REJECTED: { variant: "neutral", label: "REJECTED" },
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
    NOT_CONFIGURED: { variant: "neutral", label: "NOT CONFIGURED" },
    AUTH_REQUIRED: { variant: "warning", label: "ACCESS REQUIRED" },
  };
  const conf = map[status] || { variant: "neutral", label: status };
  return <Badge variant={conf.variant} dot={status === "ONLINE"}>{conf.label}</Badge>;
}
