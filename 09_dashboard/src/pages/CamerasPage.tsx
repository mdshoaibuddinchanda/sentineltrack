import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Camera } from "../types/api";
import { Card } from "../components/common/Card";
import { CameraStatusBadge } from "../components/common/Badge";
import { searchNearbyCameras } from "../api/cameras";
import { Video, Search, MapPin, AlertCircle } from "lucide-react";

interface CamerasPageProps {
  cameras: Camera[];
  onSelectCamera?: (cameraId: string) => void;
  selectedCameraId?: string | null;
  demoMode?: boolean;
}

export function CamerasPage({ cameras, onSelectCamera, demoMode = false }: CamerasPageProps) {
  const { cameraId: routeCameraId } = useParams<{ cameraId?: string }>();
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [selectedCam, setSelectedCam] = useState<Camera | null>(null);
  const [nearbyCams, setNearbyCams] = useState<Camera[]>([]);
  const [searchingNearby, setSearchingNearby] = useState(false);

  // Synchronize routeCameraId with cameras array (handling async load)
  useEffect(() => {
    if (routeCameraId) {
      setSelectedCam(cameras.find((c) => c.camera_id === routeCameraId) ?? null);
    } else {
      setSelectedCam((current) => current ?? cameras[0] ?? null);
    }
  }, [routeCameraId, cameras]);

  useEffect(() => {
    let cancelled = false;
    const camera = selectedCam;

    if (!camera?.latitude || !camera?.longitude) {
      setNearbyCams([]);
      setSearchingNearby(false);
      return () => {
        cancelled = true;
      };
    }

    setSearchingNearby(true);
    searchNearbyCameras(camera.latitude, camera.longitude, 5000)
      .then((res) => {
        if (!cancelled) {
          setNearbyCams(res.filter((c) => c.camera_id !== camera.camera_id));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setNearbyCams([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSearchingNearby(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedCam]);

  const filteredCameras = cameras.filter((cam) => {
    const matchesSearch =
      cam.camera_id.toLowerCase().includes(search.toLowerCase()) ||
      (cam.name && cam.name.toLowerCase().includes(search.toLowerCase())) ||
      (cam.department && cam.department.toLowerCase().includes(search.toLowerCase()));

    const matchesStatus = statusFilter === "ALL" || cam.stream_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleSelectCamera = (cam: Camera) => {
    setSelectedCam(cam);
    onSelectCamera?.(cam.camera_id);
    navigate(`/cameras/${encodeURIComponent(cam.camera_id)}`);
  };

  return (
    <div className="space-y-4">
      {demoMode && (
        <div className="source-note source-note--sample" role="status">
          <strong>Sample camera information</strong>
          <span>These connection labels are presentation fixtures. Use <code>run.bat --full</code> to inspect configured live sources.</span>
        </div>
      )}
      {/* Search & Filter Bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap bg-police-850 p-3 rounded-lg border border-police-750 font-mono text-xs">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by camera ID, location, or department"
            className="w-full bg-police-900 border border-police-700 rounded pl-9 pr-3 py-1.5 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-accent-blue"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-400">Connection status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-police-900 border border-police-700 rounded px-2.5 py-1 text-slate-200 focus:outline-none"
          >
            <option value="ALL">All ({cameras.length})</option>
            <option value="ONLINE">Online ({cameras.filter((c) => c.stream_status === "ONLINE").length})</option>
            <option value="DEGRADED">Needs attention ({cameras.filter((c) => c.stream_status === "DEGRADED").length})</option>
            <option value="OFFLINE">Offline ({cameras.filter((c) => c.stream_status === "OFFLINE").length})</option>
          </select>
        </div>
      </div>

      {/* Main Grid: Table + Detail Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Col: Camera Table */}
        <div className="lg:col-span-8">
          <Card
            title={`Registered cameras (${filteredCameras.length})`}
            subtitle="Camera connection status and recent activity"
            icon={<Video className="w-4 h-4 text-cyan-400" />}
            bodyClassName="p-0 overflow-x-auto"
          >
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-police-800/60 text-slate-400 uppercase text-[10px] border-b border-police-750">
                <tr>
                  <th className="px-3 py-2.5">Camera ID</th>
                  <th className="px-3 py-2.5">Location</th>
                  <th className="px-3 py-2.5">Department</th>
                  <th className="px-3 py-2.5">Frame rate</th>
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
            title="Camera details"
            subtitle={selectedCam ? selectedCam.camera_id : routeCameraId ? `Camera ${routeCameraId}` : "Select a camera"}
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
                    {searchingNearby && <span className="text-[10px] text-cyan-400">Checking nearby cameras…</span>}
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
                    <div className="text-[11px] text-slate-500 italic">No other cameras found within 5 km.</div>
                  )}
                </div>
              </>
            ) : routeCameraId ? (
              <div className="text-center py-8 text-amber-400 font-mono space-y-2">
                <AlertCircle className="w-6 h-6 mx-auto text-amber-400" />
                <div className="font-bold">Camera '{routeCameraId}' not found</div>
                <div className="text-[11px] text-slate-400">This camera ID is not registered in the CCTV network.</div>
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500">Select a camera from the list to inspect hardware telemetry.</div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
