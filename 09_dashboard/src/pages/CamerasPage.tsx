import React, { useState } from "react";
import { Camera } from "../types/api";
import { Card } from "../components/common/Card";
import { CameraStatusBadge } from "../components/common/Badge";
import { formatDateTime } from "../utils/formatters";
import { searchNearbyCameras } from "../api/cameras";
import { Video, Search, MapPin, Navigation, Eye, CheckCircle, AlertCircle } from "lucide-react";

interface CamerasPageProps {
  cameras: Camera[];
  onSelectCamera?: (cameraId: string) => void;
  selectedCameraId?: string | null;
}

export function CamerasPage({ cameras, onSelectCamera, selectedCameraId }: CamerasPageProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [selectedCam, setSelectedCam] = useState<Camera | null>(
    cameras.find((c) => c.camera_id === selectedCameraId) || cameras[0] || null
  );
  const [nearbyCams, setNearbyCams] = useState<Camera[]>([]);
  const [searchingNearby, setSearchingNearby] = useState(false);

  const filteredCameras = cameras.filter((cam) => {
    const matchesSearch =
      cam.camera_id.toLowerCase().includes(search.toLowerCase()) ||
      (cam.name && cam.name.toLowerCase().includes(search.toLowerCase())) ||
      (cam.department && cam.department.toLowerCase().includes(search.toLowerCase()));

    const matchesStatus = statusFilter === "ALL" || cam.stream_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleSelectCamera = async (cam: Camera) => {
    setSelectedCam(cam);
    onSelectCamera?.(cam.camera_id);

    if (cam.latitude && cam.longitude) {
      try {
        setSearchingNearby(true);
        const res = await searchNearbyCameras(cam.latitude, cam.longitude, 5000);
        setNearbyCams(res.items.filter((c) => c.camera_id !== cam.camera_id));
      } catch (e) {
        setNearbyCams([]);
      } finally {
        setSearchingNearby(false);
      }
    } else {
      setNearbyCams([]);
    }
  };

  return (
    <div className="space-y-4">
      {/* Search & Filter Bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap bg-police-850 p-3 rounded-lg border border-police-750 font-mono text-xs">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search cameras by ID, junction name, or department..."
            className="w-full bg-police-900 border border-police-700 rounded pl-9 pr-3 py-1.5 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-accent-blue"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-400">STATUS:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-police-900 border border-police-700 rounded px-2.5 py-1 text-slate-200 focus:outline-none"
          >
            <option value="ALL">ALL ({cameras.length})</option>
            <option value="ONLINE">ONLINE ({cameras.filter((c) => c.stream_status === "ONLINE").length})</option>
            <option value="DEGRADED">DEGRADED ({cameras.filter((c) => c.stream_status === "DEGRADED").length})</option>
            <option value="OFFLINE">OFFLINE ({cameras.filter((c) => c.stream_status === "OFFLINE").length})</option>
          </select>
        </div>
      </div>

      {/* Main Grid: Table + Detail Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Col: Camera Table */}
        <div className="lg:col-span-8">
          <Card
            title={`REGISTERED CCTV CAMERAS (${filteredCameras.length})`}
            subtitle="Camera ingestion network endpoints & stream health"
            icon={<Video className="w-4 h-4 text-cyan-400" />}
            bodyClassName="p-0 overflow-x-auto"
          >
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-police-800/60 text-slate-400 uppercase text-[10px] border-b border-police-750">
                <tr>
                  <th className="px-3 py-2.5">Camera ID</th>
                  <th className="px-3 py-2.5">Location / Junction</th>
                  <th className="px-3 py-2.5">Department</th>
                  <th className="px-3 py-2.5">FPS</th>
                  <th className="px-3 py-2.5">Status</th>
                  <th className="px-3 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-police-800 text-slate-300">
                {filteredCameras.map((cam) => {
                  const isSelected = selectedCam?.camera_id === cam.camera_id;
                  return (
                    <tr
                      key={cam.camera_id}
                      onClick={() => handleSelectCamera(cam)}
                      className={`cursor-pointer transition-colors ${
                        isSelected ? "bg-police-800/90 font-semibold" : "hover:bg-police-800/40"
                      }`}
                    >
                      <td className="px-3 py-2.5 font-bold text-slate-100 flex items-center gap-1.5">
                        <Video className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                        {cam.camera_id}
                      </td>
                      <td className="px-3 py-2.5 text-slate-200">{cam.name || "--"}</td>
                      <td className="px-3 py-2.5 text-slate-400">{cam.department || "--"}</td>
                      <td className="px-3 py-2.5 text-cyan-400">{cam.measured_fps ? `${cam.measured_fps} FPS` : "--"}</td>
                      <td className="px-3 py-2.5">
                        <CameraStatusBadge status={cam.stream_status} />
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectCamera(cam);
                          }}
                          className="px-2 py-0.5 bg-police-750 hover:bg-accent-blue/80 text-white rounded text-[11px]"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        </div>

        {/* Right Col: Camera Details Panel */}
        <div className="lg:col-span-4">
          <Card
            title="CAMERA NODE TELEMETRY"
            subtitle={selectedCam ? selectedCam.camera_id : "Select a camera"}
            icon={<MapPin className="w-4 h-4 text-accent-blue" />}
            bodyClassName="p-4 space-y-4 font-mono text-xs"
          >
            {selectedCam ? (
              <>
                <div className="space-y-2 border-b border-police-750 pb-3">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Stream Status:</span>
                    <CameraStatusBadge status={selectedCam.stream_status} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Department:</span>
                    <span className="text-slate-200 font-semibold">{selectedCam.department || "N/A"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Measured FPS:</span>
                    <span className="text-cyan-400 font-bold">{selectedCam.measured_fps || "--"} FPS</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Location Quality:</span>
                    <span className="text-emerald-400">{selectedCam.location_quality}</span>
                  </div>
                </div>

                <div className="space-y-1 text-slate-300">
                  <div className="text-slate-400 font-semibold mb-1">Geographic Coordinates:</div>
                  <div>Latitude: <span className="font-bold text-slate-100">{selectedCam.latitude || "--"}</span></div>
                  <div>Longitude: <span className="font-bold text-slate-100">{selectedCam.longitude || "--"}</span></div>
                  <div>Azimuth Heading: <span className="font-bold text-slate-100">{selectedCam.azimuth ? `${selectedCam.azimuth}°` : "--"}</span></div>
                </div>

                {/* Nearby Cameras in Radius */}
                <div className="pt-2 border-t border-police-750 space-y-2">
                  <div className="font-bold text-slate-300 flex items-center justify-between">
                    <span>Nearby Cameras (5 km Radius)</span>
                    {searchingNearby && <span className="text-[10px] text-cyan-400">Probing PostGIS...</span>}
                  </div>
                  {nearbyCams.length > 0 ? (
                    <div className="space-y-1.5 max-h-36 overflow-y-auto">
                      {nearbyCams.map((nc) => (
                        <div
                          key={nc.camera_id}
                          onClick={() => handleSelectCamera(nc)}
                          className="p-1.5 bg-police-900 rounded border border-police-800 flex items-center justify-between hover:bg-police-800 cursor-pointer"
                        >
                          <span className="text-[11px] text-slate-200">{nc.camera_id}</span>
                          <CameraStatusBadge status={nc.stream_status} />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-[11px] text-slate-500 italic">No other cameras within 5 km.</div>
                  )}
                </div>
              </>
            ) : (
              <div className="text-center py-8 text-slate-500">Select a camera from the list to inspect hardware telemetry.</div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
