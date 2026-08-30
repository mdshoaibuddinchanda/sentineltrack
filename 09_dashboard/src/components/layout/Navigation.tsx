import React from "react";
import { Bell, Compass, LayoutDashboard, Search, Server, Video } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

export type NavTab = "dashboard" | "cameras" | "watchlist" | "alerts" | "investigation" | "system" | "users" | "audit";

interface NavigationProps {
  unackAlertsCount: number;
}

interface NavItem {
  id: NavTab;
  path: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  badge?: number;
  visible?: boolean;
}

export function Navigation({ unackAlertsCount }: NavigationProps) {
  const location = useLocation();
  const navigate = useNavigate();

  const primaryItems: NavItem[] = [
    { id: "dashboard", path: "/operations", label: "Dashboard", description: "What needs attention now", icon: <LayoutDashboard size={19} /> },
    { id: "cameras", path: "/cameras", label: "Cameras", description: "View the camera network", icon: <Video size={19} /> },
    { id: "watchlist", path: "/targets", label: "Watchlist", description: "Manage vehicles of interest", icon: <Search size={19} /> },
    { id: "alerts", path: "/alerts", label: "Alerts", description: "Review and acknowledge alerts", icon: <Bell size={19} />, badge: unackAlertsCount },
    { id: "investigation", path: "/investigation", label: "Find a vehicle", description: "Search sightings and movement", icon: <Compass size={18} /> },
    { id: "system", path: "/system", label: "System status", description: "Connectivity and service health", icon: <Server size={18} /> },
  ];

  const isActive = (item: NavItem) =>
    location.pathname === item.path ||
    (item.id === "dashboard" && location.pathname === "/") ||
    (item.id !== "dashboard" && location.pathname.startsWith(item.path));

  const goTo = (path: string) => {
    navigate(path);
  };

  return (
    <nav className="primary-navigation" aria-label="Main navigation">
      <div className="navigation-inner">
        {primaryItems.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => goTo(item.path)}
            className={`navigation-item ${isActive(item) ? "navigation-item--active" : ""}`}
            title={item.description}
            aria-current={isActive(item) ? "page" : undefined}
          >
            {item.icon}
            <span>{item.label}</span>
            {item.badge !== undefined && item.badge > 0 && <span className="navigation-badge">{item.badge}</span>}
          </button>
        ))}

      </div>
    </nav>
  );
}
