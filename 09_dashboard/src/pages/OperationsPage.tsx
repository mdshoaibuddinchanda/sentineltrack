import React from "react";
import { MetricCards } from "../components/operations/MetricCards";
import { LiveAlertFeed } from "../components/operations/LiveAlertFeed";
import { RecentSightings } from "../components/operations/RecentSightings";
import { ControlRoomMap } from "../components/map/ControlRoomMap";
import { Card } from "../components/common/Card";
import { Camera, Alert, Sighting } from "../types/api";
import { Radio, Eye, Video } from "lucide-react";

interface OperationsPageProps {
  cameras: Camera[];
  alerts: Alert[];
  sightings: Sighting[];
  unackAlertsCount: number;
  activeTargetsCount: number;
  analyticsWorkerStatus: boolean;
  workerCount: number;
  persistedSightingsTotal?: number;
  onAcknowledgeAlert: (alertId: string) => void;
  onInvestigate: (registration: string) => void;
  onSelectCamera: (cameraId: string) => void;
  selectedCameraId?: string | null;
  privacyMode?: boolean;
}

export function OperationsPage({
  cameras,
  alerts,
  sightings,
  unackAlertsCount,
  activeTargetsCount,
  analyticsWorkerStatus,
  workerCount,
  persistedSightingsTotal,
  onAcknowledgeAlert,
  onInvestigate,
  onSelectCamera,
  selectedCameraId,
  privacyMode = false,
}: OperationsPageProps) {
  const onlineCams = cameras.filter((c) => c.stream_status === "ONLINE").length;
  const offlineCams = cameras.filter((c) => c.stream_status !== "ONLINE").length;

  return (
    <div className="space-y-4">
      {/* Top Operations KPI Metrics */}
      <MetricCards
        onlineCameras={onlineCams}
        offlineCameras={offlineCams}
        totalCameras={cameras.length}
        activeTargets={activeTargetsCount}
        unackAlerts={unackAlertsCount}
        loadedSightingsCount={sightings.length}
        persistedSightingsTotal={persistedSightingsTotal}
        analyticsStatus={analyticsWorkerStatus}
        workerCount={workerCount}
      />

      {/* Main Grid: Live Alerts & Map */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Col: Live Alert Feed */}
        <div className="lg:col-span-5 flex flex-col space-y-4">
          <Card
            title="Alerts that need review"
            subtitle="New watchlist matches from the live system"
            icon={<Radio className="w-4 h-4 text-rose-500 animate-pulse" />}
            actions={
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-police-700 text-slate-300">
                {unackAlertsCount} pending
              </span>
            }
            bodyClassName="p-3"
          >
            <LiveAlertFeed
              alerts={alerts}
              onAcknowledge={onAcknowledgeAlert}
              onInvestigate={onInvestigate}
              privacyMode={privacyMode}
            />
          </Card>
        </div>

        {/* Right Col: GIS Control Room Map */}
        <div className="lg:col-span-7 flex flex-col">
          <Card
            title="Camera network"
            subtitle="Current camera locations and vehicle observations"
            icon={<Video className="w-4 h-4 text-cyan-400" />}
            bodyClassName="p-0 overflow-hidden"
          >
            <ControlRoomMap
              cameras={cameras}
              sightings={sightings}
              selectedCameraId={selectedCameraId}
              onSelectCamera={onSelectCamera}
              privacyMode={privacyMode}
              className="h-[480px] w-full"
            />
          </Card>
        </div>
      </div>

      {/* Bottom Row: Recent Sightings Feed */}
      <Card
        title="Recent vehicle sightings"
        subtitle="Latest records received from the camera network"
        icon={<Eye className="w-4 h-4 text-accent-blue" />}
        bodyClassName="p-0"
      >
        <RecentSightings
          sightings={sightings}
          onInvestigate={onInvestigate}
          privacyMode={privacyMode}
        />
      </Card>
    </div>
  );
}
