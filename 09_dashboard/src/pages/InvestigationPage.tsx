import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTrajectory } from "../hooks/useTrajectory";
import { SearchBar } from "../components/investigation/SearchBar";
import { TrajectorySummaryCard } from "../components/investigation/TrajectorySummaryCard";
import { TrajectoryMap } from "../components/map/TrajectoryMap";
import { SightingTimeline } from "../components/investigation/SightingTimeline";
import { KinematicSegmentsTable } from "../components/investigation/KinematicSegmentsTable";
import { WarningsPanel } from "../components/investigation/WarningsPanel";
import { Card } from "../components/common/Card";
import { downloadVehicleRouteReport } from "../api/routes";
import { TableSkeleton } from "../components/common/Skeleton";
import { Compass, Download, Eye, MapPin, AlertTriangle } from "lucide-react";

interface InvestigationPageProps {
  privacyMode?: boolean;
}

export function InvestigationPage({
  privacyMode = false,
}: InvestigationPageProps) {
  const { registration: routeReg } = useParams<{ registration?: string }>();
  const navigate = useNavigate();

  const [selectedReg, setSelectedReg] = useState<string>(routeReg || "");
  const [selectedSightingId, setSelectedSightingId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (routeReg) {
      setSelectedReg(routeReg);
      setSelectedSightingId(null);
    }
  }, [routeReg]);

  const { route, summary, geoJSON, loading, error } = useTrajectory(selectedReg);

  const handleSearch = (reg: string) => {
    const clean = reg.trim().toUpperCase();
    setSelectedReg(clean);
    setSelectedSightingId(null);
    navigate(`/investigation/${encodeURIComponent(clean)}`);
  };

  const handleExport = async () => {
    if (!selectedReg || privacyMode) return;
    setExporting(true);
    setExportError(null);
    try {
      await downloadVehicleRouteReport(selectedReg);
    } catch (err: any) {
      setExportError(err?.message || "The route report could not be downloaded.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Search Bar */}
      <Card
        title="Find a vehicle"
        subtitle="Search recorded sightings and review movement between cameras"
        icon={<Compass className="w-4 h-4 text-accent-blue" />}
        actions={route && route.sightings.length > 0 ? (
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting || privacyMode}
            title={privacyMode ? "Turn off privacy mode before exporting identifying data" : "Download timestamped CSV report"}
            className="inline-flex items-center gap-1.5 rounded border border-blue-700 bg-blue-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            {exporting ? "Preparing report…" : "Download report"}
          </button>
        ) : undefined}
        bodyClassName="p-3"
      >
        <SearchBar
          initialValue={selectedReg}
          onSearch={handleSearch}
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

      {exportError && (
        <div className="rounded border border-red-700 bg-red-50 p-3 text-sm font-semibold text-slate-900 dark:bg-red-950 dark:text-white">
          {exportError}
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
          <TrajectorySummaryCard route={route} summary={summary} privacyMode={privacyMode} />

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
                title="Movement map"
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
                subtitle="Select a point to focus the map"
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
              title="Movement checks"
              subtitle="Time and distance between camera sightings"
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
