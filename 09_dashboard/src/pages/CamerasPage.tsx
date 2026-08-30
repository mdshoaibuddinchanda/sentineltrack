import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Camera } from "../types/api";
import { Card } from "../components/common/Card";
import { CameraStatusBadge } from "../components/common/Badge";
import { searchNearbyCameras, getCameraPreviewUrl } from "../api/cameras";
import { Video, Search, MapPin, AlertCircle, RefreshCw } from "lucide-react";

interface CamerasPageProps {
  cameras: Camera[];
  onSelectCamera?: (cameraId: string) => void;
  selectedCameraId?: string | null;
  liveFramesDecoded?: number;
}

export function CamerasPage({ cameras, onSelectCamera, liveFramesDecoded }: CamerasPageProps) {
  const { cameraId: routeCameraId } = useParams<{ cameraId?: string }>();
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [selectedCam, setSelectedCam] = useState<Camera | null>(null);
  const [nearbyCams, setNearbyCams] = useState<Camera[]>([]);
  const [searchingNearby, setSearchingNearby] = useState(false);
  const [previewTick, setPreviewTick] = useState(Date.now());
  const [previewFailed, setPreviewFailed] = useState(false);
  const selectedCameraId = selectedCam?.camera_id;
  const selectedLatitude = selectedCam?.latitude;
  const selectedLongitude = selectedCam?.longitude;

  // Synchronize routeCameraId with cameras array (handling async load)
  useEffect(() => {
    setSelectedCam((current) => {
      const selectedId = routeCameraId ?? current?.camera_id;
      if (selectedId) {
        return cameras.find((c) => c.camera_id === selectedId) ?? (routeCameraId ? null : cameras[0] ?? null);
      }
      return cameras[0] ?? null;
    });
  }, [routeCameraId, cameras]);

  useEffect(() => {
    let cancelled = false;

    if (selectedLatitude === undefined || selectedLatitude === null || selectedLongitude === undefined || selectedLongitude === null) {
      setNearbyCams([]);
      setSearchingNearby(false);
      return () => {
        cancelled = true;
      };
    }

    setSearchingNearby(true);
    searchNearbyCameras(selectedLatitude, selectedLongitude, 5000)
      .then((res) => {
        if (!cancelled) {
          setNearbyCams(res.filter((c) => c.camera_id !== selectedCameraId));
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
  }, [selectedCameraId, selectedLatitude, selectedLongitude]);

  useEffect(() => {
    setPreviewTick(Date.now());
    setPreviewFailed(false);
    if (!selectedCameraId) return;
    const interval = window.setInterval(() => setPreviewTick(Date.now()), 2000);
    return () => window.clearInterval(interval);
  }, [selectedCameraId]);

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
            <option value="NOT_CONFIGURED">Not configured ({cameras.filter((c) => c.stream_status === "NOT_CONFIGURED").length})</option>
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
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="font-bold text-slate-200">Camera view</div>
                    {selectedCam.stream_status === "ONLINE" && <RefreshCw className="w-3.5 h-3.5 text-emerald-400 animate-spin" />}
                  </div>
                  {selectedCam.stream_status === "ONLINE" && !previewFailed ? (
                    <img
                      src={getCameraPreviewUrl(selectedCam.camera_id, previewTick)}
                      alt={`Latest decoded frame from ${selectedCam.name || selectedCam.camera_id}`}
                      className="w-full aspect-video object-cover rounded border border-police-750 bg-black"
                      onError={() => setPreviewFailed(true)}
                    />
                  ) : (
                    <div className="flex aspect-video items-center justify-center rounded border border-police-750 bg-police-900 p-4 text-center text-xs text-slate-400">
                      {selectedCam.stream_status === "ONLINE"
                        ? "Waiting for the first decoded frame."
                        : "No live frame is available because this source is not connected."}
                    </div>
                  )}
                    <div className="text-[11px] text-slate-500">This is the latest authenticated worker snapshot, refreshed every 2 seconds.</div>
                </div>

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

                <div className="rounded border border-police-750 bg-police-900 p-3 space-y-2">
                  <div className="font-bold text-slate-200">Human verification</div>
                  <div className="text-[11px] text-slate-400">
                    {selectedCam.stream_status === "ONLINE"
                      ? "The source is connected to the analytics worker. The image above is the latest decoded worker snapshot."
                      : selectedCam.source_configured
                      ? "The source is configured, but the worker is not receiving frames from it."
                      : "This camera has no active stream source configured."}
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div><span className="text-slate-500">Source:</span> <span className="font-semibold text-slate-200">{selectedCam.source_configured ? "Configured" : "Not configured"}</span></div>
                    <div><span className="text-slate-500">Frames:</span> <span className="font-semibold text-slate-200">{selectedCam.frames_decoded ?? 0}</span></div>
                    <div><span className="text-slate-500">Sampled:</span> <span className="font-semibold text-slate-200">{selectedCam.frames_sampled ?? 0}</span></div>
                    <div><span className="text-slate-500">Reconnects:</span> <span className="font-semibold text-slate-200">{selectedCam.reconnects ?? 0}</span></div>
                  </div>
                  {liveFramesDecoded === 0 && (
                    <div className="text-[11px] font-semibold text-amber-700 dark:text-amber-300">No live frames have entered this run.</div>
                  )}
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
