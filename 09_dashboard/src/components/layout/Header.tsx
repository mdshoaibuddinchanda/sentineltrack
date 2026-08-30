import React, { useEffect, useState } from "react";
import {
  Activity,
  Bell,
  EyeOff,
  LogOut,
  Moon,
  RefreshCw,
  Shield,
  Sun,
  Video,
} from "lucide-react";

import { SystemStatusType } from "../../hooks/useSystemStatus";
import { WebSocketConnectionStatus } from "../../types/websocket";
import { useAuth } from "../../context/AuthContext";

interface HeaderProps {
  systemStatus: SystemStatusType;
  wsStatus: WebSocketConnectionStatus;
  activeCamerasCount: number;
  activeTargetsCount: number;
  unackAlertsCount: number;
  demoMode: boolean;
  darkMode: boolean;
  onToggleDarkMode: () => void;
  onRefresh: () => void;
  privacyMode: boolean;
  onTogglePrivacyMode: () => void;
}

function statusLabel(status: SystemStatusType): string {
  if (status === "HEALTHY") return "System connected";
  if (status === "DEGRADED") return "Some services need attention";
  if (status === "LOADING") return "Checking system";
  return "System disconnected";
}

function liveLabel(status: WebSocketConnectionStatus): string {
  if (status === "LIVE") return "Live updates on";
  if (status === "RECONNECTING" || status === "CONNECTING") return "Connecting to live updates";
  return "Live updates offline";
}

export function Header({
  systemStatus,
  wsStatus,
  activeCamerasCount,
  activeTargetsCount,
  unackAlertsCount,
  demoMode,
  darkMode,
  onToggleDarkMode,
  onRefresh,
  privacyMode,
  onTogglePrivacyMode,
}: HeaderProps) {
  const { user, logout } = useAuth();
  const [timeLocal, setTimeLocal] = useState("");

  useEffect(() => {
    const updateTime = () => {
      setTimeLocal(
        new Date().toLocaleTimeString("en-IN", {
          hour: "numeric",
          minute: "2-digit",
          second: "2-digit",
          hour12: true,
        }) + " IST"
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const statusClass =
    systemStatus === "HEALTHY"
      ? "status-pill status-pill--online"
      : systemStatus === "DEGRADED"
        ? "status-pill status-pill--warning"
        : "status-pill status-pill--offline";

  const liveClass =
    wsStatus === "LIVE"
      ? "connection-label connection-label--online"
      : wsStatus === "RECONNECTING" || wsStatus === "CONNECTING"
        ? "connection-label connection-label--warning"
        : "connection-label connection-label--offline";

  return (
    <header className="app-header">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true">
          <Shield size={22} strokeWidth={2.2} />
        </div>
        <div>
          <div className="brand-name">SentinelTrack</div>
          <div className="brand-subtitle">Vehicle intelligence control room</div>
        </div>
      </div>

      <div className="header-status" aria-label="System connection status">
        <span className={statusClass}>
          <span className="status-dot" aria-hidden="true" />
          {statusLabel(systemStatus)}
        </span>
        <span className={liveClass}>
          <span className="status-dot" aria-hidden="true" />
          {liveLabel(wsStatus)}
        </span>
        <span className={`data-mode ${demoMode ? "data-mode--demo" : "data-mode--live"}`}>
          {demoMode ? "Sample data" : "Live data"}
        </span>
      </div>

      <div className="header-summary" aria-label="Current counts">
        <span><Video size={16} aria-hidden="true" /> <strong>{activeCamerasCount}</strong> cameras online</span>
        <span><Activity size={16} aria-hidden="true" /> <strong>{activeTargetsCount}</strong> watchlist entries</span>
        <span className={unackAlertsCount > 0 ? "summary-alert summary-alert--active" : "summary-alert"}>
          <Bell size={16} aria-hidden="true" /> <strong>{unackAlertsCount}</strong> alerts need review
        </span>
      </div>

      <div className="header-actions">
        <span className="header-time" aria-label="Current local time">{timeLocal}</span>
        <button
          type="button"
          onClick={onTogglePrivacyMode}
          className={`icon-button ${privacyMode ? "icon-button--selected" : ""}`}
          title={privacyMode ? "Show full registration numbers" : "Hide registration numbers"}
          aria-label={privacyMode ? "Show full registration numbers" : "Hide registration numbers"}
        >
          <EyeOff size={18} />
        </button>
        <button
          type="button"
          onClick={onToggleDarkMode}
          className="icon-button"
          title={darkMode ? "Use light mode" : "Use dark mode"}
          aria-label={darkMode ? "Use light mode" : "Use dark mode"}
        >
          {darkMode ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <button
          type="button"
          onClick={onRefresh}
          className="icon-button"
          title="Refresh information"
          aria-label="Refresh information"
        >
          <RefreshCw size={18} />
        </button>
        {user && (
          <div className="user-menu">
            <div className="user-details">
              <strong>{user.username}</strong>
              <span>{user.role === "ADMIN" ? "Administrator" : user.role}</span>
            </div>
            <button
              type="button"
              onClick={() => logout()}
              className="logout-button"
              title="Sign out"
              aria-label="Sign out"
            >
              <LogOut size={17} />
              <span>Sign out</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
