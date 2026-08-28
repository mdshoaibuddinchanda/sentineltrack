import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, Video, Target, Bell, Compass, Server, Users, ShieldCheck } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

export type NavTab = "operations" | "cameras" | "targets" | "alerts" | "investigation" | "system" | "users" | "audit";

interface NavigationProps {
  unackAlertsCount: number;
}

export function Navigation({ unackAlertsCount }: NavigationProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, hasPermission } = useAuth();

  const tabs: { id: NavTab; path: string; label: string; icon: React.ReactNode; badge?: number; visible?: boolean }[] = [
    { id: "operations", path: "/operations", label: "OPERATIONS", icon: <LayoutDashboard className="w-4 h-4" /> },
    { id: "cameras", path: "/cameras", label: "CAMERAS", icon: <Video className="w-4 h-4" /> },
    { id: "targets", path: "/targets", label: "TARGETS", icon: <Target className="w-4 h-4" /> },
    { id: "alerts", path: "/alerts", label: "ALERTS", icon: <Bell className="w-4 h-4" />, badge: unackAlertsCount },
    { id: "investigation", path: "/investigation", label: "INVESTIGATION", icon: <Compass className="w-4 h-4" /> },
    { id: "system", path: "/system", label: "SYSTEM", icon: <Server className="w-4 h-4" /> },
    {
      id: "users",
      path: "/admin/users",
      label: "USERS",
      icon: <Users className="w-4 h-4" />,
      visible: user?.role === "ADMIN" || hasPermission("user:read"),
    },
    {
      id: "audit",
      path: "/audit",
      label: "AUDIT",
      icon: <ShieldCheck className="w-4 h-4" />,
      visible: user?.role === "ADMIN" || user?.role === "AUDITOR" || hasPermission("audit:read"),
    },
  ];

  const visibleTabs = tabs.filter((t) => t.visible !== false);


  const currentPath = location.pathname;

  return (
    <nav className="bg-police-850/90 border-b border-police-750 px-4 flex items-center gap-1 overflow-x-auto select-none">
      {visibleTabs.map((tab) => {

        const active =
          currentPath === tab.path ||
          (tab.id === "operations" && currentPath === "/") ||
          (tab.id !== "operations" && currentPath.startsWith(tab.path));

        return (
          <button
            key={tab.id}
            onClick={() => navigate(tab.path)}
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
