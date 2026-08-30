import React, { useState, useEffect, useCallback } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { useAuth } from "./context/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Header } from "./components/layout/Header";
import { Navigation } from "./components/layout/Navigation";
import { OfflineBanner } from "./components/common/OfflineBanner";
import { ErrorBoundary } from "./components/layout/ErrorBoundary";

import { OperationsPage } from "./pages/OperationsPage";
import { CamerasPage } from "./pages/CamerasPage";
import { TargetsPage } from "./pages/TargetsPage";
import { AlertsPage } from "./pages/AlertsPage";
import { InvestigationPage } from "./pages/InvestigationPage";
import { SystemPage } from "./pages/SystemPage";
import { UsersPage } from "./pages/UsersPage";
import { AuditPage } from "./pages/AuditPage";


import { useSystemStatus } from "./hooks/useSystemStatus";
import { useWebSocket } from "./hooks/useWebSocket";
import { useCameras } from "./hooks/useCameras";
import { useTargets } from "./hooks/useTargets";
import { useAlerts } from "./hooks/useAlerts";
import { listSightings } from "./api/sightings";
import { getAlert } from "./api/alerts";
import { Sighting } from "./types/api";
import { DEMO_SIGHTINGS } from "./utils/demoData";
import { maskRegistration } from "./utils/formatters";
import { AlertOctagon } from "lucide-react";

function DashboardApp() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [demoMode] = useState<boolean>(
    import.meta.env.VITE_DEMO_MODE === "true"
  );
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("sentineltrack-theme") === "dark";
  });
  const [privacyMode, setPrivacyMode] = useState<boolean>(false);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [sightings, setSightings] = useState<Sighting[]>([]);
  const [toastMessage, setToastMessage] = useState<{ title: string; desc: string; registration: string } | null>(null);

  // Global Subsystem Hooks (stable topic key to eliminate WebSocket churn)
  const { status: sysStatus, health, readiness, metrics, lastUpdated, error: sysError, refresh: refreshSystem } = useSystemStatus(8000, isAuthenticated);
  const { status: wsStatus, events: wsEvents } = useWebSocket("*", isAuthenticated);
  const { cameras, refresh: refreshCameras } = useCameras(undefined, demoMode, isAuthenticated);
  const { targets, create: createTarget, update: updateTarget, disable: disableTarget, refresh: refreshTargets } = useTargets(undefined, demoMode, isAuthenticated);
  const { alerts, unackCount, acknowledge: acknowledgeAlert, prependLiveAlert, refresh: refreshAlerts } = useAlerts(undefined, demoMode, isAuthenticated);

  useEffect(() => {
    document.documentElement.dataset.theme = darkMode ? "dark" : "light";
    window.localStorage.setItem("sentineltrack-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  // Initial & periodic sightings fetch
  const fetchSightings = useCallback(async () => {
    if (!isAuthenticated) {
      setSightings([]);
      return;
    }
    if (demoMode) {
      setSightings(DEMO_SIGHTINGS);
      return;
    }
    try {
      const res = await listSightings({ limit: 50 });
      setSightings(res.items);
    } catch {
      // Offline fallback
    }
  }, [demoMode, isAuthenticated]);

  useEffect(() => {
    fetchSightings();
    const interval = setInterval(fetchSightings, 12000);
    return () => clearInterval(interval);
  }, [fetchSightings]);

  // Handle incoming real-time WebSocket events with STRICT AUTHORITATIVE fetching
  useEffect(() => {
    if (wsEvents.length > 0) {
      const latest = wsEvents[0];
      if (latest.event_type === "ALERT_CREATED" && latest.data) {
        const payload = latest.data;
        const alertId = payload.alert_id;
        const rawReg = payload.registration || "UNKNOWN";
        const displayReg = maskRegistration(rawReg, privacyMode);

        // Show toast immediately with truthful received payload information
        setToastMessage({
          title: `TARGET ALERT: ${displayReg}`,
          desc: `Camera ${payload.camera_id || "N/A"}${payload.severity ? ` (${payload.severity})` : ""}`,
          registration: rawReg,
        });
        setTimeout(() => setToastMessage(null), 7000);

        // Fetch authoritative database record from backend — never synthesize fake evidence
        if (alertId && !demoMode) {
          getAlert(alertId)
            .then((authAlert) => {
              prependLiveAlert(authAlert);
            })
            .catch(() => {
              // If single-record fetch fails, trigger normal alerts list refresh
              refreshAlerts();
            });
        }
      } else if (latest.event_type === "SIGHTING_CREATED") {
        // Refetch authoritative recent sightings stream from backend
        fetchSightings();
      }
    }
  }, [wsEvents, prependLiveAlert, fetchSightings, refreshAlerts, demoMode, privacyMode]);

  const handleRefreshAll = () => {
    refreshSystem();
    refreshCameras();
    refreshTargets();
    refreshAlerts();
    fetchSightings();
  };

  const handleInvestigate = (registration: string) => {
    navigate(`/investigation/${encodeURIComponent(registration.trim().toUpperCase())}`);
  };

  const handleSelectCamera = (cameraId: string) => {
    setSelectedCameraId(cameraId);
    navigate(`/cameras/${encodeURIComponent(cameraId)}`);
  };

  return (
    <Routes>
        {/* Public route — accessible without authentication */}
        <Route path="/login" element={<LoginPage />} />

        {/* All dashboard routes are protected */}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <div className={`app-shell ${darkMode ? "theme-dark" : "theme-light"} h-screen w-screen flex flex-col overflow-hidden font-sans`}>
                {/* Top Header */}
                <Header
                  systemStatus={sysStatus}
                  wsStatus={wsStatus}
                  activeCamerasCount={cameras.filter((c) => c.stream_status === "ONLINE").length}
                  activeTargetsCount={targets.filter((t) => t.enabled).length}
                  unackAlertsCount={unackCount}
                  demoMode={demoMode}
                  darkMode={darkMode}
                  onToggleDarkMode={() => setDarkMode((prev) => !prev)}
                  onRefresh={handleRefreshAll}
                  privacyMode={privacyMode}
                  onTogglePrivacyMode={() => setPrivacyMode((prev) => !prev)}
                />

                {/* Offline / Degraded Banner */}
                <OfflineBanner
                  status={sysStatus}
                  error={sysError}
                  onRetry={refreshSystem}
                  degradedDetails={readiness?.components}
                />

                {/* Primary Navigation */}
                <Navigation unackAlertsCount={unackCount} />

                {/* Toast Notification */}
                {toastMessage && (
                  <div
                    onClick={() => {
                      handleInvestigate(toastMessage.registration);
                      setToastMessage(null);
                    }}
                    className="alert-toast"
                  >
                    <div className="alert-toast__title">
                      <AlertOctagon className="w-4 h-4" />
                      <span>{toastMessage.title}</span>
                    </div>
                    <div className="alert-toast__description">{toastMessage.desc}</div>
                    <div className="alert-toast__action">Select to view the vehicle record →</div>
                  </div>
                )}

                {/* Main Content View Container with Router */}
                <main className="app-main flex-1 p-4 overflow-y-auto">
                  <ErrorBoundary fallbackTitle="Page Display Error">
                    <Routes>
                      <Route path="/" element={<Navigate to="/operations" replace />} />
                      <Route
                        path="/operations"
                        element={
                          <OperationsPage
                            cameras={cameras}
                            alerts={alerts}
                            sightings={sightings}
                            unackAlertsCount={unackCount}
                            activeTargetsCount={targets.filter((t) => t.enabled).length}
                            analyticsWorkerStatus={readiness?.components?.analytics_worker === true}
                            workerCount={metrics?.active_camera_workers ?? 0}
                            persistedSightingsTotal={metrics?.total_sightings_persisted}
                            onAcknowledgeAlert={acknowledgeAlert}
                            onInvestigate={handleInvestigate}
                            onSelectCamera={handleSelectCamera}
                            selectedCameraId={selectedCameraId}
                            privacyMode={privacyMode}
                          />
                        }
                      />
                      <Route
                        path="/cameras"
                        element={
                          <CamerasPage
                            cameras={cameras}
                            onSelectCamera={handleSelectCamera}
                            selectedCameraId={selectedCameraId}
                          />
                        }
                      />
                      <Route
                        path="/cameras/:cameraId"
                        element={
                          <CamerasPage
                            cameras={cameras}
                            onSelectCamera={handleSelectCamera}
                            selectedCameraId={selectedCameraId}
                          />
                        }
                      />
                      <Route
                        path="/targets"
                        element={
                          <TargetsPage
                            targets={targets}
                            onCreateTarget={createTarget}
                            onUpdateTarget={updateTarget}
                            onDisableTarget={disableTarget}
                            onInvestigate={handleInvestigate}
                            privacyMode={privacyMode}
                          />
                        }
                      />
                      <Route
                        path="/alerts"
                        element={
                          <AlertsPage
                            alerts={alerts}
                            onAcknowledge={acknowledgeAlert}
                            onInvestigate={handleInvestigate}
                            privacyMode={privacyMode}
                          />
                        }
                      />
                      <Route
                        path="/alerts/:alertId"
                        element={
                          <AlertsPage
                            alerts={alerts}
                            onAcknowledge={acknowledgeAlert}
                            onInvestigate={handleInvestigate}
                            privacyMode={privacyMode}
                          />
                        }
                      />
                      <Route
                        path="/investigation"
                        element={
                          <InvestigationPage
                            demoMode={demoMode}
                            privacyMode={privacyMode}
                          />
                        }
                      />
                      <Route
                        path="/investigation/:registration"
                        element={
                          <InvestigationPage
                            demoMode={demoMode}
                            privacyMode={privacyMode}
                          />
                        }
                      />
                      <Route
                        path="/system"
                        element={
                          <SystemPage
                          health={health}
                          readiness={readiness}
                          metrics={metrics}
                          lastUpdated={lastUpdated}
                          onRefresh={refreshSystem}
                          />
                        }
                      />
                      <Route
                        path="/admin/users"
                        element={
                          <ProtectedRoute requiredRole="ADMIN">
                            <UsersPage />
                          </ProtectedRoute>
                        }
                      />
                      <Route
                        path="/audit"
                        element={
                          <ProtectedRoute requiredPermission="audit:read">
                            <AuditPage />
                          </ProtectedRoute>
                        }
                      />
                      <Route path="*" element={<Navigate to="/operations" replace />} />

                    </Routes>
                  </ErrorBoundary>
                </main>
              </div>
            </ProtectedRoute>
          }
        />
    </Routes>
  );
}

export function App() {
  return (
    <AuthProvider>
      <DashboardApp />
    </AuthProvider>
  );
}
