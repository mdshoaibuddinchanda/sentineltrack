import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import { Camera, Sighting } from "../../types/api";
import { formatDateTime, maskRegistration } from "../../utils/formatters";
import { CameraStatusBadge, TimeQualityBadge } from "../common/Badge";
import { MapLegend } from "./MapLegend";
import { Video } from "lucide-react";

interface ControlRoomMapProps {
  cameras: Camera[];
  sightings?: Sighting[];
  selectedCameraId?: string | null;
  onSelectCamera?: (cameraId: string) => void;
  privacyMode?: boolean;
  className?: string;
}

// Leaflet DivIcon helpers
function createCameraIcon(status: string, isSelected: boolean) {
  const color = status === "ONLINE" ? "#10b981" : status === "DEGRADED" ? "#f59e0b" : "#ef4444";
  const ring = isSelected ? "ring-4 ring-cyan-400 scale-125" : "";
  return L.divIcon({
    className: "custom-camera-marker",
    html: `
      <div class="relative flex items-center justify-center w-6 h-6 rounded-full bg-police-900 border-2 shadow-lg transition-transform ${ring}" style="border-color: ${color}">
        <div class="w-2 h-2 rounded-full" style="background-color: ${color}"></div>
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
  });
}

function createSightingIcon() {
  return L.divIcon({
    className: "custom-sighting-marker",
    html: `
      <div class="relative flex items-center justify-center w-7 h-7 rounded-full bg-cyan-950 border-2 border-cyan-400 shadow-xl animate-pulse">
        <span class="text-[10px] font-bold text-cyan-300 font-mono">HIT</span>
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
}

function AutoBoundsController({ positions }: { positions: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length > 0) {
      const bounds = L.latLngBounds(positions.map(([lat, lng]) => [lat, lng]));
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [positions, map]);
  return null;
}

export function ControlRoomMap({
  cameras,
  sightings = [],
  selectedCameraId,
  onSelectCamera,
  privacyMode = false,
  className = "h-[450px] w-full",
}: ControlRoomMapProps) {
  const [tileError, setTileError] = useState(false);

  const validCameras = cameras.filter(
    (c) => c.latitude !== undefined && c.longitude !== undefined && !isNaN(c.latitude!) && !isNaN(c.longitude!)
  );

  const positions: [number, number][] = validCameras.map((c) => [c.latitude!, c.longitude!]);

  // Default center (Ahmedabad coordinate center)
  const defaultCenter: [number, number] = [23.0225, 72.5714];

  return (
    <div className={`relative rounded-lg overflow-hidden border border-police-750/90 shadow-2xl ${className}`}>
      <MapContainer
        center={positions.length > 0 ? positions[0] : defaultCenter}
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

        {positions.length > 0 && <AutoBoundsController positions={positions} />}

        {/* Camera Markers */}
        {validCameras.map((cam) => (
          <Marker
            key={cam.camera_id}
            position={[cam.latitude!, cam.longitude!]}
            icon={createCameraIcon(cam.stream_status, selectedCameraId === cam.camera_id)}
            eventHandlers={{
              click: () => onSelectCamera?.(cam.camera_id),
            }}
          >
            <Popup className="tactical-popup">
              <div className="p-2 space-y-2 min-w-[220px]">
                <div className="flex items-center justify-between border-b border-police-700 pb-1.5">
                  <span className="font-bold text-xs text-slate-100 font-mono">{cam.camera_id}</span>
                  <CameraStatusBadge status={cam.stream_status} />
                </div>
                <div className="text-xs text-slate-300 font-semibold">{cam.name || "CCTV Node"}</div>
                <div className="text-[11px] text-slate-400">{cam.department || "Surveillance"}</div>
                <div className="text-[10px] text-slate-400 font-mono">
                  Coordinates: {cam.latitude?.toFixed(4)}, {cam.longitude?.toFixed(4)}
                </div>
                {cam.measured_fps && (
                  <div className="text-[11px] text-cyan-400 font-mono">Measured: {cam.measured_fps} FPS</div>
                )}
                {onSelectCamera && (
                  <button
                    onClick={() => onSelectCamera(cam.camera_id)}
                    className="w-full mt-1.5 py-1 px-2 bg-police-700 hover:bg-accent-blue/80 text-white rounded text-[11px] font-semibold transition-colors flex items-center justify-center gap-1"
                  >
                    <Video className="w-3 h-3" /> Focus Camera
                  </button>
                )}
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Sighting Overlay Markers */}
        {sightings.map((s) => {
          const cam = cameras.find((c) => c.camera_id === s.camera_id);
          if (!cam || !cam.latitude || !cam.longitude) return null;
          return (
            <Marker key={s.sighting_id} position={[cam.latitude, cam.longitude]} icon={createSightingIcon()}>
              <Popup>
                <div className="p-2 space-y-1.5 min-w-[200px]">
                  <div className="text-xs font-bold text-cyan-300 font-mono">TARGET SIGHTING</div>
                  <div className="text-sm font-bold text-white font-mono">
                    {maskRegistration(s.registration_candidate, privacyMode)}
                  </div>
                  <div className="text-[11px] text-slate-300">Camera: {s.camera_id}</div>
                  <div className="text-[11px] text-slate-400">{formatDateTime(s.event_time_utc || s.created_at)}</div>
                  <div className="text-[11px] text-cyan-400 font-mono">Match Score: {s.match_score.toFixed(2)}</div>
                  <TimeQualityBadge quality={s.event_time_quality} />
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      <MapLegend />

      {tileError && (
        <div className="absolute top-2 right-2 z-[1000] bg-police-850/90 border border-amber-600/80 text-amber-300 px-2.5 py-1 rounded text-[11px] font-mono shadow-lg">
          Basemap tile network offline — vector geospatial overlay active
        </div>
      )}
    </div>
  );
}
