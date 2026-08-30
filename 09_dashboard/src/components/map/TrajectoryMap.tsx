import React, { useEffect, useState } from "react";
import { GeoJSON as LeafletGeoJSON, MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import { RouteResponse, GeoJSONFeatureCollection } from "../../types/api";
import { formatDateTime, formatDistance, formatSpeed, maskRegistration } from "../../utils/formatters";
import { FeasibilityBadge, TimeQualityBadge } from "../common/Badge";
import { MapLegend } from "./MapLegend";
import { Info } from "lucide-react";

interface TrajectoryMapProps {
  route: RouteResponse | null;
  geoJSON?: GeoJSONFeatureCollection | null;
  selectedSightingId?: string | null;
  onSelectSighting?: (sightingId: string) => void;
  privacyMode?: boolean;
  className?: string;
}

function createSequenceIcon(sequence: number, isSelected: boolean) {
  const ring = isSelected ? "ring-4 ring-cyan-400 scale-125 bg-cyan-600" : "bg-police-800";
  return L.divIcon({
    className: "custom-seq-marker",
    html: `
      <div class="relative flex items-center justify-center w-7 h-7 rounded-full border-2 border-cyan-400 shadow-2xl text-cyan-200 font-mono text-xs font-bold transition-all ${ring}">
        ${sequence}
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
}

function TrajectoryBoundsController({ sightings }: { sightings: { latitude?: number | null; longitude?: number | null }[] }) {
  const map = useMap();
  useEffect(() => {
    const valid = sightings.filter(
      (s): s is typeof s & { latitude: number; longitude: number } =>
        typeof s.latitude === "number" && Number.isFinite(s.latitude) &&
        typeof s.longitude === "number" && Number.isFinite(s.longitude)
    );
    if (valid.length > 0) {
      const bounds = L.latLngBounds(valid.map((s) => [s.latitude!, s.longitude!]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 14 });
    }
  }, [sightings, map]);
  return null;
}

export function TrajectoryMap({
  route,
  geoJSON,
  selectedSightingId,
  onSelectSighting,
  privacyMode = false,
  className = "h-[500px] w-full",
}: TrajectoryMapProps) {
  const [tileError, setTileError] = useState(false);

  const sightings = route?.sightings || [];
  const validSightings = sightings.filter(
    (s): s is typeof s & { latitude: number; longitude: number } =>
      typeof s.latitude === "number" && Number.isFinite(s.latitude) &&
      typeof s.longitude === "number" && Number.isFinite(s.longitude)
  );
  const incomingSegments = new Map((route?.segments || []).map((segment) => [segment.to_sighting_id, segment]));

  const polylineCoords: [number, number][] = validSightings.map((s) => [s.latitude!, s.longitude!]);

  const defaultCenter: [number, number] = [23.0225, 72.5714];

  return (
    <div className={`relative rounded-lg overflow-hidden border border-police-750/90 shadow-2xl ${className}`}>
      <MapContainer
        center={polylineCoords.length > 0 ? polylineCoords[0] : defaultCenter}
        zoom={12}
        className="h-full w-full bg-police-900"
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
          eventHandlers={{
            tileerror: () => setTileError(true),
          }}
        />

        {validSightings.length > 0 && <TrajectoryBoundsController sightings={validSightings} />}

        {geoJSON && geoJSON.features.length > 0 && (
          <LeafletGeoJSON
            data={geoJSON as never}
            style={{ color: "#22d3ee", weight: 2, opacity: 0.7, dashArray: "5, 7" }}
            pointToLayer={(_feature, latlng) =>
              L.circleMarker(latlng, {
                radius: 5,
                color: "#67e8f9",
                fillColor: "#0891b2",
                fillOpacity: 0.8,
              })
            }
          />
        )}

        {/* Trajectory Polyline */}
        {polylineCoords.length >= 2 && (
          <Polyline
            positions={polylineCoords}
            pathOptions={{
              color: route?.status === "CONFLICTING_SIGHTINGS" ? "#ef4444" : "#06b6d4",
              weight: 4,
              opacity: 0.85,
              dashArray: route?.status === "AMBIGUOUS" ? "6, 8" : undefined,
            }}
          />
        )}

        {/* Sequence Node Markers */}
        {validSightings.map((s, idx) => (
          <Marker
            key={s.sighting_id}
            position={[s.latitude!, s.longitude!]}
            icon={createSequenceIcon(idx + 1, selectedSightingId === s.sighting_id)}
            eventHandlers={{
              click: () => onSelectSighting?.(s.sighting_id),
            }}
          >
            <Popup className="tactical-popup">
              <div className="p-2 space-y-1.5 min-w-[210px]">
                <div className="flex items-center justify-between border-b border-police-700 pb-1">
                  <span className="font-bold text-xs text-cyan-300 font-mono">Node #{idx + 1}</span>
                  <span className="text-[10px] text-slate-400 font-mono">{s.camera_id}</span>
                </div>
                <div className="text-[11px] text-slate-300 font-mono">
                  Target: <span className="text-slate-100">{maskRegistration(route?.registration || "", privacyMode)}</span>
                </div>
                <div className="text-xs text-slate-200">{formatDateTime(s.event_time_utc)}</div>
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-slate-400">Match Score:</span>
                  <span className="text-slate-100 font-semibold">{s.match_score.toFixed(2)}</span>
                </div>
                <TimeQualityBadge quality={s.time_quality} />
                {incomingSegments.has(s.sighting_id) && (
                  <div className="pt-1 border-t border-police-700 space-y-1">
                    <div className="text-[10px] text-slate-400">Incoming transition</div>
                    <div className="text-[11px] text-slate-300">
                      {formatDistance(incomingSegments.get(s.sighting_id)?.distance_lower_bound_m)} at {formatSpeed(incomingSegments.get(s.sighting_id)?.minimum_required_speed_kmh)}
                    </div>
                    <FeasibilityBadge feasibility={incomingSegments.get(s.sighting_id)?.feasibility || "UNKNOWN"} />
                  </div>
                )}
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      <MapLegend />

      {/* Trajectory Disclaimer Badge */}
      <div className="absolute top-3 left-3 z-[1000] max-w-sm bg-police-900/90 border border-police-700/90 rounded p-2 text-[10px] text-slate-400 backdrop-blur-sm flex items-start gap-1.5 shadow-lg">
        <Info className="w-3.5 h-3.5 text-accent-blue shrink-0 mt-0.5" />
        <span>
          <strong>Chronological CCTV Trajectory:</strong> Vector connects observed camera sightings in time sequence. Does not represent reconstructed road-level polyline.
        </span>
      </div>

      {tileError && (
        <div className="absolute top-3 right-3 z-[1000] bg-police-850/90 border border-amber-600/80 text-amber-300 px-2.5 py-1 rounded text-[11px] font-mono shadow-lg">
          Offline Tile Mode Active
        </div>
      )}
    </div>
  );
}
