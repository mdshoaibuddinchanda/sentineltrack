import React, { useState, useEffect, useCallback } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
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

export function App() {
  const navigate = useNavigate();
  const [demoMode, setDemoMode] = useState<boolean>(
    import.meta.env.VITE_DEMO_MODE === "true"
  );
  const [privacyMode, setPrivacyMode] = useState<boolean>(false);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [sightings, setSightings] = useState<Sighting[]>([]);
  const [toastMessage, setToastMessage] = useState<{ title: string; desc: string; registration: string } | null>(null);

  // Global Subsystem Hooks (stable topic key to eliminate WebSocket churn)
  const { status: sysStatus, health, readiness, metrics, error: sysError, refresh: refreshSystem } = useSystemStatus(8000);
  const { status: wsStatus, events: wsEvents } = useWebSocket("*");
  const { cameras, refresh: refreshCameras } = useCameras(undefined, demoMode);
  const { targets, create: createTarget, update: updateTarget, disable: disableTarget, refresh: refreshTargets } = useTargets(undefined, demoMode);
  const { alerts, unackCount, acknowledge: acknowledgeAlert, prependLiveAlert, refresh: refreshAlerts } = useAlerts(undefined, demoMode);

  // Initial & periodic sightings fetch
  const fetchSightings = useCallback(async () => {
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
  }, [demoMode]);

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
          desc: `Camera ${payload.camera_id || "N/A"} (${payload.severity || "CRITICAL"})`,
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
    <div className="h-screen w-screen flex flex-col bg-police-900 text-slate-100 overflow-hidden font-sans">
      {/* Top Header */}
      <Header
        systemStatus={sysStatus}
        wsStatus={wsStatus}
        activeCamerasCount={cameras.filter((c) => c.stream_status === "ONLINE").length}
        activeTargetsCount={targets.filter((t) => t.enabled).length}
        unackAlertsCount={unackCount}
        demoMode={demoMode}
        onToggleDemoMode={() => setDemoMode((prev) => !prev)}
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
          className="fixed top-20 right-4 z-50 p-3 bg-rose-950 border-2 border-rose-600 rounded-lg shadow-2xl text-white cursor-pointer hover:bg-rose-900 transition-all animate-bounce max-w-sm"
        >
          <div className="flex items-center gap-2 font-mono font-bold text-xs text-rose-300">
            <AlertOctagon className="w-4 h-4 text-rose-400 animate-pulse" />
            <span>{toastMessage.title}</span>
          </div>
          <div className="text-[11px] text-slate-200 mt-1 font-mono">{toastMessage.desc}</div>
          <div className="text-[10px] text-cyan-300 font-semibold mt-1 font-mono">Click to open GIS trajectory &rarr;</div>
        </div>
      )}

      {/* Main Content View Container with Router */}
      <main className="flex-1 p-4 overflow-y-auto bg-police-900/60">
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
                  onRefresh={refreshSystem}
                />
              }
            />
            <Route path="*" element={<Navigate to="/operations" replace />} />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  );
}
