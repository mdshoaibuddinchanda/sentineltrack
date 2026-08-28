import React, { useState, useEffect } from "react";
import { Shield, Radio, Activity, AlertOctagon, Video, RefreshCw, Lock, LogOut } from "lucide-react";

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
  onToggleDemoMode: () => void;
  onRefresh: () => void;
  privacyMode: boolean;
  onTogglePrivacyMode: () => void;
}

export function Header({
  systemStatus,
  wsStatus,
  activeCamerasCount,
  activeTargetsCount,
  unackAlertsCount,
  demoMode,
  onToggleDemoMode,
  onRefresh,
  privacyMode,
  onTogglePrivacyMode,
}: HeaderProps) {
  const { user, logout } = useAuth();
  const [timeUtc, setTimeUtc] = useState("");
  const [timeLocal, setTimeLocal] = useState("");


  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeUtc(now.toISOString().substring(11, 19) + " UTC");
      setTimeLocal(
        now.toLocaleTimeString("en-IN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }) + " IST"
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const getStatusBadge = () => {
    switch (systemStatus) {
      case "HEALTHY":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-600/50">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            ONLINE
          </span>
        );
      case "DEGRADED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold bg-amber-950/80 text-amber-300 border border-amber-600/50">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            DEGRADED
          </span>
        );
      case "OFFLINE":
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold bg-rose-950/80 text-rose-300 border border-rose-600/50">
            <span className="w-2 h-2 rounded-full bg-rose-400" />
            OFFLINE
          </span>
        );
    }
  };

  const getWsBadge = () => {
    switch (wsStatus) {
      case "LIVE":
        return (
          <span className="inline-flex items-center gap-1 text-xs text-cyan-400 font-mono" title="Live WebSocket Event Hub Connected">
            <Radio className="w-3.5 h-3.5 animate-pulse" /> LIVE WS
          </span>
        );
      case "RECONNECTING":
        return (
          <span className="inline-flex items-center gap-1 text-xs text-amber-400 font-mono" title="Reconnecting WebSocket">
            <Radio className="w-3.5 h-3.5 animate-spin" /> RECONNECTING
          </span>
        );
      case "CONNECTING":
        return (
          <span className="inline-flex items-center gap-1 text-xs text-slate-400 font-mono">
            <Radio className="w-3.5 h-3.5" /> CONNECTING
          </span>
        );
      case "OFFLINE":
      default:
        return (
          <span className="inline-flex items-center gap-1 text-xs text-rose-400 font-mono" title="WebSocket Disconnected">
            <Radio className="w-3.5 h-3.5" /> WS OFFLINE
          </span>
        );
    }
  };

  return (
    <header className="bg-police-900/95 border-b border-police-750/80 px-4 py-2.5 flex items-center justify-between gap-4 z-40">
      {/* Brand & Badge */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded bg-accent-blue/20 border border-accent-blue/50 flex items-center justify-center text-accent-blue shadow-lg shadow-accent-blue/10">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold tracking-wider text-white font-mono">SENTINELTRACK</span>
              <span className="text-[10px] uppercase px-1.5 py-0.2 bg-police-700 text-slate-300 rounded border border-police-600 font-mono">
                v1.0.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden sm:block">Real-Time CCTV Vehicle Intelligence Control Room</p>
          </div>
        </div>

        <div className="h-5 w-[1px] bg-police-700 mx-1 hidden sm:block" />

        <div className="flex items-center gap-2">
          {getStatusBadge()}
          {getWsBadge()}
        </div>
      </div>

      {/* Real-Time Operational Counters */}
      <div className="hidden md:flex items-center gap-4 text-xs font-mono">
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-police-850 rounded border border-police-750">
          <Video className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-slate-400">CAMERAS:</span>
          <span className="font-semibold text-slate-100">{activeCamerasCount}</span>
        </div>

        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-police-850 rounded border border-police-750">
          <Activity className="w-3.5 h-3.5 text-accent-blue" />
          <span className="text-slate-400">TARGETS:</span>
          <span className="font-semibold text-slate-100">{activeTargetsCount}</span>
        </div>

        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded border ${
          unackAlertsCount > 0 ? "bg-rose-950/80 border-rose-700 text-rose-200 animate-pulse" : "bg-police-850 border-police-750 text-slate-400"
        }`}>
          <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
          <span>ALERTS:</span>
          <span className="font-bold text-slate-100">{unackAlertsCount}</span>
        </div>
      </div>

      {/* Clock & Controls */}
      <div className="flex items-center gap-3">
        <div className="text-right hidden lg:block font-mono">
          <div className="text-xs font-semibold text-slate-200">{timeLocal}</div>
          <div className="text-[11px] text-slate-400">{timeUtc}</div>
        </div>

        <button
          onClick={onTogglePrivacyMode}
          title={privacyMode ? "Disable plate masking" : "Enable plate masking (Presentation Mode)"}
          className={`p-1.5 rounded border text-xs flex items-center gap-1 transition-colors ${
            privacyMode ? "bg-accent-blue/30 border-accent-blue text-accent-blue" : "bg-police-800 border-police-700 text-slate-400 hover:text-white"
          }`}
        >
          <Lock className="w-3.5 h-3.5" />
          <span className="hidden sm:inline text-[11px]">{privacyMode ? "Masked" : "Redact"}</span>
        </button>

        <button
          onClick={onToggleDemoMode}
          title={demoMode ? "Disable simulated demo fixtures" : "Enable simulated Ahmedabad demo fixtures"}
          className={`px-2 py-1 rounded border text-xs font-mono font-semibold transition-colors ${
            demoMode ? "bg-cyan-950 border-cyan-600 text-cyan-300" : "bg-police-800 border-police-700 text-slate-400 hover:text-white"
          }`}
        >
          {demoMode ? "DEMO: ON" : "DEMO: OFF"}
        </button>

        <button
          onClick={onRefresh}
          title="Manual refresh all views"
          className="p-1.5 bg-police-800 hover:bg-police-700 border border-police-700 rounded text-slate-300 hover:text-white transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
        </button>

        {/* Authenticated User & Logout */}
        {user && (
          <div className="flex items-center gap-2 pl-2 border-l border-police-700">
            <div className="hidden sm:flex flex-col text-right font-mono">
              <span className="text-xs font-bold text-slate-200">{user.username}</span>
              <span className="text-[10px] text-cyan-400 font-semibold">{user.role}</span>
            </div>
            <button
              onClick={() => logout()}
              title="Sign Out / Terminate Session"
              className="p-1.5 bg-rose-950/60 hover:bg-rose-900 border border-rose-700/60 rounded text-rose-300 hover:text-white transition-colors flex items-center gap-1 text-xs font-mono"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden md:inline text-[11px]">Logout</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
}

