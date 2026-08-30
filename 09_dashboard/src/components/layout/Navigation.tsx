import React, { useEffect, useRef, useState } from "react";
import { Bell, ChevronDown, Compass, LayoutDashboard, MoreHorizontal, Search, Server, ShieldCheck, Users, Video } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

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
  const { user, hasPermission } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const closeMenu = (event: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(event.target as Node)) {
        setMoreOpen(false);
      }
    };
    document.addEventListener("mousedown", closeMenu);
    return () => document.removeEventListener("mousedown", closeMenu);
  }, []);

  const primaryItems: NavItem[] = [
    { id: "dashboard", path: "/operations", label: "Dashboard", description: "What needs attention now", icon: <LayoutDashboard size={19} /> },
    { id: "cameras", path: "/cameras", label: "Cameras", description: "View the camera network", icon: <Video size={19} /> },
    { id: "watchlist", path: "/targets", label: "Watchlist", description: "Manage vehicles of interest", icon: <Search size={19} /> },
    { id: "alerts", path: "/alerts", label: "Alerts", description: "Review and acknowledge alerts", icon: <Bell size={19} />, badge: unackAlertsCount },
  ];

  const moreItems: NavItem[] = [
    { id: "investigation", path: "/investigation", label: "Find a vehicle", description: "Search sightings and movement", icon: <Compass size={18} /> },
    { id: "system", path: "/system", label: "System status", description: "Connectivity and service health", icon: <Server size={18} /> },
    {
      id: "users",
      path: "/admin/users",
      label: "Users and access",
      description: "Manage operator accounts",
      icon: <Users size={18} />,
      visible: user?.role === "ADMIN" || hasPermission("user:read"),
    },
    {
      id: "audit",
      path: "/audit",
      label: "Security log",
      description: "Review recorded actions",
      icon: <ShieldCheck size={18} />,
      visible: user?.role === "ADMIN" || user?.role === "AUDITOR" || hasPermission("audit:read"),
    },
  ];

  const isActive = (item: NavItem) =>
    location.pathname === item.path ||
    (item.id === "dashboard" && location.pathname === "/") ||
    (item.id !== "dashboard" && location.pathname.startsWith(item.path));

  const goTo = (path: string) => {
    setMoreOpen(false);
    navigate(path);
  };

  const moreActive = moreItems.some((item) => item.visible !== false && isActive(item));

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

        <div className="more-navigation" ref={moreRef}>
          <button
            type="button"
            onClick={() => setMoreOpen((open) => !open)}
            className={`navigation-item navigation-item--more ${moreActive ? "navigation-item--active" : ""}`}
            aria-expanded={moreOpen}
            aria-haspopup="menu"
          >
            <MoreHorizontal size={19} />
            <span>More</span>
            <ChevronDown size={16} className={moreOpen ? "chevron-up" : ""} />
          </button>
          {moreOpen && (
            <div className="more-menu" role="menu">
              <div className="more-menu-heading">More pages</div>
              {moreItems.filter((item) => item.visible !== false).map((item) => (
                <button key={item.id} type="button" role="menuitem" onClick={() => goTo(item.path)} className={`more-menu-item ${isActive(item) ? "more-menu-item--active" : ""}`}>
                  {item.icon}
                  <span>
                    <strong>{item.label}</strong>
                    <small>{item.description}</small>
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
