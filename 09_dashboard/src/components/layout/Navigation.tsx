import React from "react";
import { LayoutDashboard, Video, Target, Bell, Compass, Server } from "lucide-react";

export type NavTab = "operations" | "cameras" | "targets" | "alerts" | "investigation" | "system";

interface NavigationProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  unackAlertsCount: number;
}

export function Navigation({ currentTab, onSelectTab, unackAlertsCount }: NavigationProps) {
  const tabs: { id: NavTab; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: "operations", label: "OPERATIONS", icon: <LayoutDashboard className="w-4 h-4" /> },
    { id: "cameras", label: "CAMERAS", icon: <Video className="w-4 h-4" /> },
    { id: "targets", label: "TARGETS", icon: <Target className="w-4 h-4" /> },
    { id: "alerts", label: "ALERTS", icon: <Bell className="w-4 h-4" />, badge: unackAlertsCount },
    { id: "investigation", label: "INVESTIGATION", icon: <Compass className="w-4 h-4" /> },
    { id: "system", label: "SYSTEM", icon: <Server className="w-4 h-4" /> },
  ];

  return (
    <nav className="bg-police-850/90 border-b border-police-750 px-4 flex items-center gap-1 overflow-x-auto select-none">
      {tabs.map((tab) => {
        const active = currentTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onSelectTab(tab.id)}
            className={`flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold tracking-wider font-mono uppercase transition-colors relative ${
              active
                ? "text-accent-blue bg-police-800/80 border-b-2 border-accent-blue"
                : "text-slate-400 hover:text-slate-200 hover:bg-police-800/40"
            }`}
          >
            {tab.icon}
            <span>{tab.label}</span>
            {tab.badge !== undefined && tab.badge > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-rose-600 text-white font-sans animate-pulse">
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
