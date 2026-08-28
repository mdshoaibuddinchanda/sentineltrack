import React, { useState, useEffect, useCallback } from "react";
import { Header } from "./components/layout/Header";
import { Navigation, NavTab } from "./components/layout/Navigation";
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
import { Sighting, Alert } from "./types/api";
import { DEMO_SIGHTINGS } from "./utils/demoData";
import { Bell, CheckCircle2, AlertOctagon } from "lucide-react";

export function App() {
  const [currentTab, setCurrentTab] = useState<NavTab>("operations");
  const [demoMode, setDemoMode] = useState<boolean>(
    import.meta.env.VITE_DEMO_MODE === "true"
  );
  const [privacyMode, setPrivacyMode] = useState<boolean>(false);
  const [investigationPlate, setInvestigationPlate] = useState<string>("GJ01AB1234");
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [sightings, setSightings] = useState<Sighting[]>([]);
  const [toastMessage, setToastMessage] = useState<{ title: string; desc: string; type: "alert" | "info" } | null>(null);

  // Global Subsystem Hooks
  const { status: sysStatus, health, readiness, metrics, error: sysError, refresh: refreshSystem } = useSystemStatus(8000);
  const { status: wsStatus, events: wsEvents } = useWebSocket(["*"]);
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
      // Fallback
    }
  }, [demoMode]);

  useEffect(() => {
    fetchSightings();
    const interval = setInterval(fetchSightings, 12000);
    return () => clearInterval(interval);
  }, [fetchSightings]);

  // Handle incoming real-time WebSocket events
  useEffect(() => {
    if (wsEvents.length > 0) {
      const latest = wsEvents[0];
      if (latest.event_type === "ALERT_CREATED" && latest.data) {
        const payload = latest.data;
        const liveAlt: Alert = {
          alert_id: payload.alert_id || `alt_live_${Date.now()}`,
          watchlist_id: payload.watchlist_id || "",
          sighting_id: payload.sighting_id || "",
          camera_id: payload.camera_id || "unknown_camera",
          stream_epoch: 1,
          track_id: 1,
          registration: payload.registration || "UNKNOWN",
          match_score: payload.match_score || 0.95,
          match_class: "EXACT",
          severity: payload.severity || "CRITICAL",
          created_at: latest.timestamp || new Date().toISOString(),
          acknowledged: false,
          explanation: [`Live alert triggered at camera ${payload.camera_id} with match score ${(payload.match_score || 0.95).toFixed(2)}`],
        };
        prependLiveAlert(liveAlt);

        // Show toast
        setToastMessage({
          title: `TARGET ALERT: ${payload.registration}`,
          desc: `Detected at camera ${payload.camera_id} (${payload.severity || "CRITICAL"})`,
          type: "alert",
        });
        setTimeout(() => setToastMessage(null), 6000);
      } else if (latest.event_type === "SIGHTING_CREATED" && latest.data) {
        const p = latest.data;
        const liveSight: Sighting = {
          sighting_id: p.sighting_id || `sight_live_${Date.now()}`,
          camera_id: p.camera_id || "camera",
          stream_epoch: 1,
          track_id: 1,
          first_pts_ms: 0,
          last_pts_ms: 0,
          registration_candidate: p.registration,
          confidence: 0.95,
          match_score: p.match_score || 0.95,
          match_class: p.match_class || "EXACT",
          created_at: latest.timestamp || new Date().toISOString(),
          event_time_utc: latest.timestamp || new Date().toISOString(),
          event_time_quality: "HIGH",
        };
        setSightings((prev) => [liveSight, ...prev.slice(0, 49)]);
      }
    }
  }, [wsEvents, prependLiveAlert]);

  const handleRefreshAll = () => {
    refreshSystem();
    refreshCameras();
    refreshTargets();
    refreshAlerts();
    fetchSightings();
  };

  const handleInvestigate = (registration: string) => {
    setInvestigationPlate(registration);
    setCurrentTab("investigation");
  };

  const handleSelectCamera = (cameraId: string) => {
    setSelectedCameraId(cameraId);
    if (currentTab !== "cameras" && currentTab !== "operations") {
      setCurrentTab("cameras");
    }
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
      <Navigation
        currentTab={currentTab}
        onSelectTab={(tab) => setCurrentTab(tab)}
        unackAlertsCount={unackCount}
      />

      {/* Toast Notification Notification */}
      {toastMessage && (
        <div
          onClick={() => {
            const plate = toastMessage.title.replace("TARGET ALERT: ", "");
            handleInvestigate(plate);
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

      {/* Main Content View Container */}
      <main className="flex-1 p-4 overflow-y-auto bg-police-900/60">
        <ErrorBoundary fallbackTitle="Page Display Error">
          {currentTab === "operations" && (
            <OperationsPage
              cameras={cameras}
              alerts={alerts}
              sightings={sightings}
              unackAlertsCount={unackCount}
              activeTargetsCount={targets.filter((t) => t.enabled).length}
              analyticsWorkerStatus={Boolean(readiness?.components?.analytics_worker ?? true)}
              workerCount={metrics?.active_camera_workers || cameras.filter((c) => c.stream_status === "ONLINE").length}
              onAcknowledgeAlert={acknowledgeAlert}
              onInvestigate={handleInvestigate}
              onSelectCamera={handleSelectCamera}
              selectedCameraId={selectedCameraId}
              privacyMode={privacyMode}
            />
          )}

          {currentTab === "cameras" && (
            <CamerasPage
              cameras={cameras}
              onSelectCamera={handleSelectCamera}
              selectedCameraId={selectedCameraId}
            />
          )}

          {currentTab === "targets" && (
            <TargetsPage
              targets={targets}
              onCreateTarget={createTarget}
              onUpdateTarget={updateTarget}
              onDisableTarget={disableTarget}
              onInvestigate={handleInvestigate}
              privacyMode={privacyMode}
            />
          )}

          {currentTab === "alerts" && (
            <AlertsPage
              alerts={alerts}
              onAcknowledge={acknowledgeAlert}
              onInvestigate={handleInvestigate}
              privacyMode={privacyMode}
            />
          )}

          {currentTab === "investigation" && (
            <InvestigationPage
              initialRegistration={investigationPlate}
              demoMode={demoMode}
              privacyMode={privacyMode}
            />
          )}

          {currentTab === "system" && (
            <SystemPage
              health={health}
              readiness={readiness}
              metrics={metrics}
              lastUpdated={new Date()}
              onRefresh={refreshSystem}
            />
          )}
        </ErrorBoundary>
      </main>
    </div>
  );
}
