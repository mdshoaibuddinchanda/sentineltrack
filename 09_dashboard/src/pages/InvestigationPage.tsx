import React, { useState } from "react";
import { useTrajectory } from "../hooks/useTrajectory";
import { SearchBar } from "../components/investigation/SearchBar";
import { TrajectorySummaryCard } from "../components/investigation/TrajectorySummaryCard";
import { TrajectoryMap } from "../components/map/TrajectoryMap";
import { SightingTimeline } from "../components/investigation/SightingTimeline";
import { KinematicSegmentsTable } from "../components/investigation/KinematicSegmentsTable";
import { WarningsPanel } from "../components/investigation/WarningsPanel";
import { Card } from "../components/common/Card";
import { TableSkeleton } from "../components/common/Skeleton";
import { Compass, Eye, MapPin, AlertTriangle, CheckCircle } from "lucide-react";

interface InvestigationPageProps {
  initialRegistration?: string;
  demoMode?: boolean;
  privacyMode?: boolean;
}

export function InvestigationPage({
  initialRegistration = "GJ01AB1234",
  demoMode = false,
  privacyMode = false,
}: InvestigationPageProps) {
  const [selectedReg, setSelectedReg] = useState(initialRegistration);
  const [selectedSightingId, setSelectedSightingId] = useState<string | null>(null);

  const { route, summary, geoJSON, sightings, loading, error, refresh } = useTrajectory(
    selectedReg,
    demoMode
  );

  return (
    <div className="space-y-4">
      {/* Top Search Bar */}
      <Card
        title="CROSS-CAMERA VEHICLE TRAJECTORY INVESTIGATION"
        subtitle="Query vehicle observation history and reconstruct spatio-temporal route"
        icon={<Compass className="w-4 h-4 text-accent-blue" />}
        bodyClassName="p-3"
      >
        <SearchBar
          initialValue={selectedReg}
          onSearch={(reg) => {
            setSelectedReg(reg);
            setSelectedSightingId(null);
          }}
          isLoading={loading}
        />
      </Card>

      {/* Error state */}
      {error && !loading && (
        <div className="p-4 bg-police-850 border border-police-700 rounded-lg text-slate-300 font-mono text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <Card>
          <TableSkeleton rows={4} cols={4} />
        </Card>
      )}

      {route && !loading && (
        <>
          {/* Summary Metric Strip */}
          <TrajectorySummaryCard route={route} summary={summary} />

          {/* Conflict & Ambiguity Warning Panels */}
          <WarningsPanel
            status={route.status}
            reasons={route.reasons}
            warnings={route.warnings}
          />

          {/* Main Map & Sighting Timeline Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Left Col: Trajectory Map */}
            <div className="lg:col-span-8 flex flex-col">
              <Card
                title="CHRONOLOGICAL GIS TRAJECTORY MAP"
                subtitle="Sequential observation nodes connected in time order"
                icon={<MapPin className="w-4 h-4 text-cyan-400" />}
                bodyClassName="p-0 overflow-hidden"
              >
                <TrajectoryMap
                  route={route}
                  geoJSON={geoJSON}
                  selectedSightingId={selectedSightingId}
                  onSelectSighting={(sId) => setSelectedSightingId(sId)}
                  privacyMode={privacyMode}
                  className="h-[520px] w-full"
                />
              </Card>
            </div>

            {/* Right Col: Sighting Timeline */}
            <div className="lg:col-span-4 flex flex-col">
              <Card
                title={`SIGHTING TIMELINE (${route.sightings.length})`}
                subtitle="Click node to synchronize map marker"
                icon={<Eye className="w-4 h-4 text-accent-blue" />}
                bodyClassName="p-4 overflow-y-auto max-h-[520px]"
              >
                <SightingTimeline
                  sightings={route.sightings}
                  selectedSightingId={selectedSightingId}
                  onSelectSighting={(sId) => setSelectedSightingId(sId)}
                  privacyMode={privacyMode}
                />
              </Card>
            </div>
          </div>

          {/* Bottom Table: Kinematic Segment Feasibility */}
          {route.segments && route.segments.length > 0 && (
            <Card
              title="KINEMATIC SEGMENT TRANSITION ANALYSIS"
              subtitle="Inter-camera transit duration, lower-bound distance, and minimum required speed"
              icon={<Compass className="w-4 h-4 text-emerald-400" />}
              bodyClassName="p-0"
            >
              <KinematicSegmentsTable segments={route.segments} />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
