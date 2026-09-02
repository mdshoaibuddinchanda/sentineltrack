import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Camera as CameraIcon,
  Database,
  Download,
  FileUp,
  MapPinned,
  PlugZap,
  Plus,
  RefreshCw,
  Route as RouteIcon,
  ShieldCheck,
} from "lucide-react";

import {
  analyzeCameraCoverage,
  bulkImportCameras,
  createCamera,
  downloadCameraGapAnalysis,
  downloadCameraGeoJSON,
  getCameraGapAnalysis,
  listVMSConnectors,
  syncVMSConnector,
  updateCamera,
} from "../../api/cameras";
import { checkCameraPairFeasibility } from "../../api/routes";
import type {
  Camera,
  CameraBulkImportResponse,
  CameraGapAnalysisResponse,
  CameraImportMode,
  CameraPairFeasibilityResponse,
  CameraRegistryInput,
  CoverageAnalysisResponse,
  LocationQuality,
  VMSConnectorStatus,
} from "../../types/api";
import { downloadCameraCsvTemplate, parseCameraCsv } from "../../utils/cameraRegistry";
import { Card } from "../common/Card";
import { Modal } from "../common/Modal";

type ToolModal = "register" | "edit" | "import" | "gis" | null;

interface CameraRegistryToolsProps {
  cameras: Camera[];
  selectedCamera: Camera | null;
  canManage: boolean;
  onChanged: () => void | Promise<void>;
}

interface RegistryFormState {
  camera_id: string;
  name: string;
  department: string;
  organization: string;
  source_system: string;
  external_id: string;
  latitude: string;
  longitude: string;
  location_quality: LocationQuality;
  coordinate_source: string;
  coordinate_accuracy_m: string;
  azimuth: string;
  coverage_radius_m: string;
  field_of_view_degrees: string;
  rtsp_url: string;
  hls_url: string;
  webrtc_url: string;
  live: boolean;
}

const EMPTY_FORM: RegistryFormState = {
  camera_id: "",
  name: "",
  department: "",
  organization: "",
  source_system: "MANUAL",
  external_id: "",
  latitude: "",
  longitude: "",
  location_quality: "UNKNOWN",
  coordinate_source: "",
  coordinate_accuracy_m: "",
  azimuth: "",
  coverage_radius_m: "",
  field_of_view_degrees: "",
  rtsp_url: "",
  hls_url: "",
  webrtc_url: "",
  live: true,
};

const inputClass = "w-full rounded border border-police-700 bg-police-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-accent-blue focus:outline-none";
const secondaryButton = "inline-flex items-center justify-center gap-2 rounded border border-police-600 bg-police-800 px-3 py-2 text-xs font-semibold text-slate-100 hover:border-accent-blue disabled:cursor-not-allowed disabled:opacity-50";
const primaryButton = "inline-flex items-center justify-center gap-2 rounded border border-blue-700 bg-blue-700 px-3 py-2 text-xs font-bold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50";

function textOrUndefined(value: string): string | undefined {
  const normalized = value.trim();
  return normalized || undefined;
}

function numberOrUndefined(value: string, label: string): number | undefined {
  const normalized = value.trim();
  if (!normalized) return undefined;
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) throw new Error(`${label} must be a number.`);
  return parsed;
}

function payloadFromForm(form: RegistryFormState): CameraRegistryInput {
  const latitude = numberOrUndefined(form.latitude, "Latitude");
  const longitude = numberOrUndefined(form.longitude, "Longitude");
  if ((latitude === undefined) !== (longitude === undefined)) {
    throw new Error("Latitude and longitude must be entered together.");
  }
  if (latitude !== undefined && !form.coordinate_source.trim()) {
    throw new Error("State the coordinate source, such as an official survey or VMS record.");
  }

  return {
    camera_id: form.camera_id.trim(),
    name: textOrUndefined(form.name),
    department: textOrUndefined(form.department),
    organization: textOrUndefined(form.organization),
    source_system: textOrUndefined(form.source_system) || "MANUAL",
    external_id: textOrUndefined(form.external_id) || form.camera_id.trim(),
    latitude,
    longitude,
    location_quality: latitude === undefined ? "UNKNOWN" : form.location_quality,
    coordinate_source: textOrUndefined(form.coordinate_source),
    coordinate_accuracy_m: numberOrUndefined(form.coordinate_accuracy_m, "Coordinate accuracy"),
    azimuth: numberOrUndefined(form.azimuth, "Azimuth"),
    coverage_radius_m: numberOrUndefined(form.coverage_radius_m, "Coverage radius"),
    field_of_view_degrees: numberOrUndefined(form.field_of_view_degrees, "Field of view"),
    rtsp_url: textOrUndefined(form.rtsp_url),
    hls_url: textOrUndefined(form.hls_url),
    webrtc_url: textOrUndefined(form.webrtc_url),
    live: form.live,
    metadata: {},
  };
}

function formFromCamera(camera: Camera): RegistryFormState {
  const value = (item: string | number | null | undefined) => item == null ? "" : String(item);
  return {
    ...EMPTY_FORM,
    camera_id: camera.camera_id,
    name: camera.name || "",
    department: camera.department || "",
    organization: camera.organization || "",
    source_system: camera.source_system || "MANUAL",
    external_id: camera.external_id || camera.camera_id,
    latitude: value(camera.latitude),
    longitude: value(camera.longitude),
    location_quality: camera.location_quality,
    coordinate_source: camera.coordinate_source || "",
    coordinate_accuracy_m: value(camera.coordinate_accuracy_m),
    azimuth: value(camera.azimuth),
    coverage_radius_m: value(camera.coverage_radius_m),
    field_of_view_degrees: value(camera.field_of_view_degrees),
    live: camera.live,
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The operation could not be completed.";
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1.5 text-xs font-semibold text-slate-300">
      <span>{label}</span>
      {children}
      {hint && <span className="block text-[11px] font-normal leading-4 text-slate-500">{hint}</span>}
    </label>
  );
}

function Metric({ label, value, warning = false }: { label: string; value: string; warning?: boolean }) {
  return (
    <div className="rounded border border-police-750 bg-police-900 px-3 py-2">
      <div className="text-[11px] font-semibold text-slate-400">{label}</div>
      <div className={`mt-0.5 text-lg font-bold ${warning ? "text-amber-300" : "text-slate-100"}`}>{value}</div>
    </div>
  );
}

export function CameraRegistryTools({ cameras, selectedCamera, canManage, onChanged }: CameraRegistryToolsProps) {
  const [activeModal, setActiveModal] = useState<ToolModal>(null);
  const [form, setForm] = useState<RegistryFormState>(EMPTY_FORM);
  const [gap, setGap] = useState<CameraGapAnalysisResponse | null>(null);
  const [connectors, setConnectors] = useState<VMSConnectorStatus[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(true);
  const [panelError, setPanelError] = useState<string | null>(null);
  const [panelMessage, setPanelMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [csvCameras, setCsvCameras] = useState<CameraRegistryInput[]>([]);
  const [csvFilename, setCsvFilename] = useState("");
  const [importMode, setImportMode] = useState<CameraImportMode>("CREATE_ONLY");
  const [importResult, setImportResult] = useState<CameraBulkImportResponse | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  const geolocated = useMemo(
    () => cameras.filter((camera) => camera.latitude != null && camera.longitude != null),
    [cameras],
  );
  const [fromCameraId, setFromCameraId] = useState("");
  const [toCameraId, setToCameraId] = useState("");
  const [elapsedMinutes, setElapsedMinutes] = useState("10");
  const [routeResult, setRouteResult] = useState<CameraPairFeasibilityResponse | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [aoiGeoJson, setAoiGeoJson] = useState("");
  const [coverageRadius, setCoverageRadius] = useState("100");
  const [includeApproximate, setIncludeApproximate] = useState(false);
  const [coverageResult, setCoverageResult] = useState<CoverageAnalysisResponse | null>(null);
  const [coverageError, setCoverageError] = useState<string | null>(null);

  const refreshEvidence = useCallback(async () => {
    setEvidenceLoading(true);
    setPanelError(null);
    const [gapResult, connectorResult] = await Promise.allSettled([
      getCameraGapAnalysis(),
      listVMSConnectors(),
    ]);
    if (gapResult.status === "fulfilled") setGap(gapResult.value);
    if (connectorResult.status === "fulfilled") setConnectors(connectorResult.value.items);
    if (gapResult.status === "rejected" || connectorResult.status === "rejected") {
      setPanelError("Registry evidence is temporarily unavailable. Camera viewing is unaffected.");
    }
    setEvidenceLoading(false);
  }, []);

  useEffect(() => {
    refreshEvidence();
  }, [refreshEvidence]);

  useEffect(() => {
    if (!fromCameraId && geolocated[0]) setFromCameraId(geolocated[0].camera_id);
    if (!toCameraId && geolocated[1]) setToCameraId(geolocated[1].camera_id);
  }, [fromCameraId, geolocated, toCameraId]);

  const openRegister = () => {
    setForm(EMPTY_FORM);
    setPanelError(null);
    setPanelMessage(null);
    setActiveModal("register");
  };

  const openEdit = () => {
    if (!selectedCamera) return;
    setForm(formFromCamera(selectedCamera));
    setPanelError(null);
    setPanelMessage(null);
    setActiveModal("edit");
  };

  const closeModal = () => {
    if (saving) return;
    setActiveModal(null);
  };

  const saveRegistry = async () => {
    setSaving(true);
    setPanelError(null);
    try {
      const payload = payloadFromForm(form);
      if (!payload.camera_id) throw new Error("Camera ID is required.");
      const result = activeModal === "edit"
        ? await updateCamera(payload.camera_id, {
            name: payload.name,
            department: payload.department,
            organization: payload.organization,
            source_system: payload.source_system,
            external_id: payload.external_id,
            latitude: payload.latitude,
            longitude: payload.longitude,
            location_quality: payload.location_quality,
            coordinate_source: payload.coordinate_source,
            coordinate_accuracy_m: payload.coordinate_accuracy_m,
            azimuth: payload.azimuth,
            coverage_radius_m: payload.coverage_radius_m,
            field_of_view_degrees: payload.field_of_view_degrees,
            ...(payload.rtsp_url ? { rtsp_url: payload.rtsp_url } : {}),
            ...(payload.hls_url ? { hls_url: payload.hls_url } : {}),
            ...(payload.webrtc_url ? { webrtc_url: payload.webrtc_url } : {}),
            live: payload.live,
          })
        : await createCamera(payload);
      setPanelMessage(`${result.camera.camera_id} ${result.created ? "was registered" : "was updated"}. Worker status: ${result.worker_status.replace(/_/g, " ").toLowerCase()}.`);
      setActiveModal(null);
      await onChanged();
      await refreshEvidence();
    } catch (error) {
      setPanelError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const handleCsvFile = async (file: File | undefined) => {
    setImportError(null);
    setImportResult(null);
    setCsvCameras([]);
    setCsvFilename(file?.name || "");
    if (!file) return;
    try {
      const records = parseCameraCsv(await file.text());
      setCsvCameras(records);
      const result = await bulkImportCameras(records, { mode: importMode, dry_run: true });
      setImportResult(result);
    } catch (error) {
      setImportError(errorMessage(error));
    }
  };

  const validateImportAgain = async () => {
    if (csvCameras.length === 0) return;
    setSaving(true);
    setImportError(null);
    try {
      setImportResult(await bulkImportCameras(csvCameras, { mode: importMode, dry_run: true }));
    } catch (error) {
      setImportError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const applyImport = async () => {
    if (!importResult || importResult.valid === 0) return;
    setSaving(true);
    setImportError(null);
    try {
      const result = await bulkImportCameras(csvCameras, { mode: importMode, dry_run: false });
      setImportResult(result);
      setPanelMessage(`Camera import complete: ${result.created} created, ${result.updated} updated, ${result.skipped} skipped.`);
      await onChanged();
      await refreshEvidence();
    } catch (error) {
      setImportError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const runRouteCheck = async () => {
    setRouteError(null);
    setRouteResult(null);
    try {
      const minutes = Number(elapsedMinutes);
      if (!fromCameraId || !toCameraId || fromCameraId === toCameraId) {
        throw new Error("Choose two different geolocated cameras.");
      }
      if (!Number.isFinite(minutes) || minutes <= 0) throw new Error("Elapsed time must be greater than zero.");
      setRouteResult(await checkCameraPairFeasibility({
        from_camera_id: fromCameraId,
        to_camera_id: toCameraId,
        elapsed_seconds: minutes * 60,
      }));
    } catch (error) {
      setRouteError(errorMessage(error));
    }
  };

  const runCoverage = async () => {
    setCoverageError(null);
    setCoverageResult(null);
    try {
      const parsed = JSON.parse(aoiGeoJson) as Record<string, unknown>;
      const radius = Number(coverageRadius);
      if (!Number.isFinite(radius) || radius < 10) throw new Error("Coverage radius must be at least 10 metres.");
      setCoverageResult(await analyzeCameraCoverage({
        area_of_interest: parsed,
        default_coverage_radius_m: radius,
        include_approximate: includeApproximate,
      }));
    } catch (error) {
      setCoverageError(errorMessage(error));
    }
  };

  const exportArtifact = async (kind: "gap" | "geojson") => {
    setPanelError(null);
    try {
      const filename = kind === "gap" ? await downloadCameraGapAnalysis() : await downloadCameraGeoJSON();
      setPanelMessage(`Downloaded ${filename}.`);
    } catch (error) {
      setPanelError(errorMessage(error));
    }
  };

  const runConnector = async (connector: VMSConnectorStatus, dryRun: boolean) => {
    setSaving(true);
    setPanelError(null);
    try {
      const result = await syncVMSConnector(connector.connector_id, { mode: "UPSERT", dry_run: dryRun });
      setPanelMessage(
        dryRun
          ? `${connector.organization}: validation found ${result.valid} valid camera records; nothing was changed.`
          : `${connector.organization}: ${result.created} cameras created and ${result.updated} updated.`,
      );
      if (!dryRun) await onChanged();
      await refreshEvidence();
    } catch (error) {
      setPanelError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const readyConnectors = connectors.filter((connector) => connector.ready).length;
  const geolocatedCount = gap?.geolocated_cameras ?? geolocated.length;
  const totalCount = gap?.total_cameras ?? cameras.length;

  return (
    <>
      <Card
        title="Camera setup and GIS"
        subtitle="Register sources, complete GPS metadata, validate integrations, and test movement feasibility"
        icon={<Database className="h-4 w-4 text-cyan-400" />}
        actions={
          <button type="button" onClick={refreshEvidence} className={secondaryButton} disabled={evidenceLoading}>
            <RefreshCw className={`h-3.5 w-3.5 ${evidenceLoading ? "animate-spin" : ""}`} />
            Refresh evidence
          </button>
        }
        bodyClassName="space-y-4"
      >
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <Metric label="GPS recorded" value={`${geolocatedCount} / ${totalCount}`} warning={totalCount > 0 && geolocatedCount < totalCount} />
          <Metric label="Verified GPS" value={String(gap?.verified_coordinates ?? cameras.filter((camera) => camera.location_quality === "VERIFIED").length)} />
          <Metric label="Missing stream source" value={String(gap?.missing_stream_source ?? "—")} warning={(gap?.missing_stream_source ?? 0) > 0} />
          <Metric label="VMS connectors ready" value={`${readyConnectors} / ${connectors.length}`} warning={connectors.length > readyConnectors} />
        </div>

        <div className="flex flex-wrap gap-2">
          {canManage && (
            <button type="button" onClick={openRegister} className={primaryButton}>
              <Plus className="h-4 w-4" /> Register camera
            </button>
          )}
          {canManage && (
            <button type="button" onClick={openEdit} className={secondaryButton} disabled={!selectedCamera}>
              <CameraIcon className="h-4 w-4" /> Edit selected camera
            </button>
          )}
          {canManage && (
            <button type="button" onClick={() => setActiveModal("import")} className={secondaryButton}>
              <FileUp className="h-4 w-4" /> Import camera CSV
            </button>
          )}
          <button type="button" onClick={() => setActiveModal("gis")} className={secondaryButton}>
            <RouteIcon className="h-4 w-4" /> GIS demonstration
          </button>
          <button type="button" onClick={() => exportArtifact("gap")} className={secondaryButton}>
            <Download className="h-4 w-4" /> Gap report CSV
          </button>
          <button type="button" onClick={() => exportArtifact("geojson")} className={secondaryButton}>
            <MapPinned className="h-4 w-4" /> Camera map GeoJSON
          </button>
        </div>

        {panelMessage && <div role="status" className="rounded border border-emerald-700 bg-emerald-950 p-3 text-xs font-semibold text-emerald-200">{panelMessage}</div>}
        {panelError && <div role="alert" className="rounded border border-amber-600 bg-amber-950 p-3 text-xs font-semibold text-amber-200">{panelError}</div>}

        <details className="rounded border border-police-750 bg-police-900">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-xs font-bold text-slate-200">
            <span className="flex items-center gap-2"><PlugZap className="h-4 w-4 text-cyan-400" /> View organization integration readiness</span>
            <span className="text-[11px] font-semibold text-slate-400">{readyConnectors} of {connectors.length} ready</span>
          </summary>
          {connectors.length === 0 ? (
            <div className="border-t border-police-750 px-3 py-3 text-xs text-slate-400">No connector definitions are configured.</div>
          ) : (
            <div className="divide-y divide-police-750 border-t border-police-750">
              {connectors.map((connector) => (
                <div key={connector.connector_id} className="flex flex-col gap-2 px-3 py-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2 text-xs font-bold text-slate-100">
                      <span>{connector.organization}</span>
                      <span className={`operator-badge rounded px-2 py-0.5 text-[10px] ${connector.ready ? "operator-badge--success" : "operator-badge--warning"}`}>
                        {connector.ready ? "READY" : connector.enabled ? "SETUP REQUIRED" : "DISABLED TEMPLATE"}
                      </span>
                    </div>
                    <div className="mt-1 text-[11px] text-slate-400">
                      {connector.connector_type.replace(/_/g, " ")} · {connector.endpoint_host || "endpoint not set"} · {connector.readiness_message}
                    </div>
                  </div>
                  {canManage && connector.ready && (
                    <div className="flex shrink-0 gap-2">
                      <button type="button" className={secondaryButton} disabled={saving} onClick={() => runConnector(connector, true)}>Validate</button>
                      <button type="button" className={primaryButton} disabled={saving} onClick={() => runConnector(connector, false)}>Sync cameras</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </details>

        <div className="flex items-start gap-2 text-[11px] leading-4 text-slate-400">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
          GPS is accepted only with its source and quality. Stream credentials are never accepted in camera URLs or registry metadata.
        </div>
      </Card>

      <Modal
        isOpen={activeModal === "register" || activeModal === "edit"}
        onClose={closeModal}
        title={activeModal === "edit" ? `Edit ${form.camera_id}` : "Register a camera"}
        maxWidth="2xl"
        footer={
          <>
            <button type="button" onClick={closeModal} className={secondaryButton} disabled={saving}>Cancel</button>
            <button type="button" onClick={saveRegistry} className={primaryButton} disabled={saving}>
              {saving ? "Saving…" : activeModal === "edit" ? "Save camera" : "Register camera"}
            </button>
          </>
        }
      >
        <div className="space-y-5">
          <section className="space-y-3">
            <div>
              <h4 className="text-sm font-bold text-slate-100">Identity and ownership</h4>
              <p className="mt-1 text-xs text-slate-400">Use the source organization’s durable identifiers. Camera IDs cannot be changed later.</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="Camera ID *"><input aria-label="Camera ID" className={inputClass} value={form.camera_id} disabled={activeModal === "edit"} onChange={(event) => setForm({ ...form, camera_id: event.target.value })} placeholder="cam-ahmedabad-001" /></Field>
              <Field label="Location name"><input aria-label="Location name" className={inputClass} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Paldi Circle" /></Field>
              <Field label="Department"><input aria-label="Department" className={inputClass} value={form.department} onChange={(event) => setForm({ ...form, department: event.target.value })} placeholder="Traffic Police" /></Field>
              <Field label="Organization"><input aria-label="Organization" className={inputClass} value={form.organization} onChange={(event) => setForm({ ...form, organization: event.target.value })} placeholder="Ahmedabad City Police" /></Field>
              <Field label="Source system"><input aria-label="Source system" className={inputClass} value={form.source_system} onChange={(event) => setForm({ ...form, source_system: event.target.value })} /></Field>
              <Field label="External source ID"><input aria-label="External source ID" className={inputClass} value={form.external_id} onChange={(event) => setForm({ ...form, external_id: event.target.value })} placeholder="Defaults to camera ID" /></Field>
            </div>
          </section>

          <section className="space-y-3 border-t border-police-750 pt-4">
            <div>
              <h4 className="text-sm font-bold text-slate-100">GPS and coverage metadata</h4>
              <p className="mt-1 text-xs text-slate-400">WGS84 coordinates are not guessed. Enter authoritative values and record where they came from.</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="Latitude"><input aria-label="Latitude" className={inputClass} value={form.latitude} onChange={(event) => setForm({ ...form, latitude: event.target.value })} placeholder="23.0225" /></Field>
              <Field label="Longitude"><input aria-label="Longitude" className={inputClass} value={form.longitude} onChange={(event) => setForm({ ...form, longitude: event.target.value })} placeholder="72.5714" /></Field>
              <Field label="Coordinate quality">
                <select aria-label="Coordinate quality" className={inputClass} value={form.location_quality} onChange={(event) => setForm({ ...form, location_quality: event.target.value as LocationQuality })}>
                  <option value="UNKNOWN">Unknown</option><option value="APPROXIMATE">Approximate</option><option value="VERIFIED">Verified</option>
                </select>
              </Field>
              <Field label="Coordinate source" hint="Required when latitude and longitude are entered."><input aria-label="Coordinate source" className={inputClass} value={form.coordinate_source} onChange={(event) => setForm({ ...form, coordinate_source: event.target.value })} placeholder="Official GIS survey, record number…" /></Field>
              <Field label="Accuracy (metres)"><input aria-label="Coordinate accuracy" className={inputClass} value={form.coordinate_accuracy_m} onChange={(event) => setForm({ ...form, coordinate_accuracy_m: event.target.value })} /></Field>
              <Field label="Camera heading (0–359°)"><input aria-label="Camera heading" className={inputClass} value={form.azimuth} onChange={(event) => setForm({ ...form, azimuth: event.target.value })} /></Field>
              <Field label="Planning radius (metres)"><input aria-label="Planning radius" className={inputClass} value={form.coverage_radius_m} onChange={(event) => setForm({ ...form, coverage_radius_m: event.target.value })} placeholder="100" /></Field>
              <Field label="Field of view (degrees)"><input aria-label="Field of view" className={inputClass} value={form.field_of_view_degrees} onChange={(event) => setForm({ ...form, field_of_view_degrees: event.target.value })} /></Field>
            </div>
          </section>

          <section className="space-y-3 border-t border-police-750 pt-4">
            <div>
              <h4 className="text-sm font-bold text-slate-100">Live stream source</h4>
              <p className="mt-1 text-xs text-slate-400">Use public service URLs without embedded usernames, passwords, tokens, or cookies. {activeModal === "edit" ? "Leave these fields blank to keep the current endpoints." : "At least one endpoint is recommended."}</p>
            </div>
            <div className="grid gap-3">
              <Field label="RTSP URL"><input aria-label="RTSP URL" className={inputClass} value={form.rtsp_url} onChange={(event) => setForm({ ...form, rtsp_url: event.target.value })} placeholder="rtsp://host:8554/stream/camera" /></Field>
              <Field label="HLS URL"><input aria-label="HLS URL" className={inputClass} value={form.hls_url} onChange={(event) => setForm({ ...form, hls_url: event.target.value })} placeholder="https://host/camera/index.m3u8" /></Field>
              <Field label="WebRTC/WHEP URL"><input aria-label="WebRTC WHEP URL" className={inputClass} value={form.webrtc_url} onChange={(event) => setForm({ ...form, webrtc_url: event.target.value })} placeholder="https://host/stream/camera/whep" /></Field>
              <label className="flex items-center gap-2 text-xs font-semibold text-slate-200"><input type="checkbox" checked={form.live} onChange={(event) => setForm({ ...form, live: event.target.checked })} /> Enable this source for processing</label>
            </div>
          </section>
          {panelError && <div role="alert" className="rounded border border-amber-600 bg-amber-950 p-3 text-xs font-semibold text-amber-200">{panelError}</div>}
        </div>
      </Modal>

      <Modal
        isOpen={activeModal === "import"}
        onClose={closeModal}
        title="Import a camera list"
        maxWidth="xl"
        footer={<button type="button" onClick={closeModal} className={secondaryButton} disabled={saving}>Close</button>}
      >
        <div className="space-y-4 text-xs">
          <div className="rounded border border-blue-700 bg-blue-950 p-3 text-blue-200">
            Every file is validated first. Applying an import is a separate, audited action. Maximum 500 cameras per batch.
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Import behavior">
              <select aria-label="Import behavior" className={inputClass} value={importMode} onChange={(event) => { setImportMode(event.target.value as CameraImportMode); setImportResult(null); }}>
                <option value="CREATE_ONLY">Create new cameras only</option>
                <option value="UPSERT">Create new and update existing</option>
              </select>
            </Field>
            <button type="button" className={secondaryButton} onClick={downloadCameraCsvTemplate}><Download className="h-4 w-4" /> Download template</button>
          </div>
          <Field label="Camera CSV file" hint="Required header: camera_id. GPS rows also require coordinate_source.">
            <input aria-label="Camera CSV file" type="file" accept=".csv,text/csv" className={inputClass} onChange={(event) => handleCsvFile(event.target.files?.[0])} />
          </Field>
          {csvFilename && <div className="text-slate-400">Selected: {csvFilename} · {csvCameras.length} parsed rows</div>}
          {importError && <div role="alert" className="rounded border border-amber-600 bg-amber-950 p-3 font-semibold text-amber-200">{importError}</div>}
          {csvCameras.length > 0 && !importResult && (
            <button type="button" className={primaryButton} disabled={saving} onClick={validateImportAgain}>{saving ? "Validating…" : "Validate file"}</button>
          )}
          {importResult && (
            <div className="space-y-3 rounded border border-police-750 bg-police-900 p-3">
              <div className="grid grid-cols-3 gap-2">
                <Metric label="Received" value={String(importResult.received)} />
                <Metric label="Valid" value={String(importResult.valid)} warning={importResult.valid < importResult.received} />
                <Metric label="Skipped" value={String(importResult.skipped)} warning={importResult.skipped > 0} />
              </div>
              <div className="max-h-40 overflow-y-auto rounded border border-police-750">
                {importResult.items.map((item) => <div key={`${item.row}-${item.camera_id}`} className="flex gap-3 border-b border-police-750 px-2 py-1.5 last:border-b-0"><span className="w-12 text-slate-500">Row {item.row}</span><span className="min-w-32 font-semibold text-slate-200">{item.camera_id}</span><span className="text-slate-400">{item.message}</span></div>)}
              </div>
              {importResult.dry_run ? (
                <button type="button" className={primaryButton} onClick={applyImport} disabled={saving || importResult.valid === 0}>{saving ? "Importing…" : "Apply validated import"}</button>
              ) : <div role="status" className="font-bold text-emerald-300">Import applied successfully.</div>}
            </div>
          )}
        </div>
      </Modal>

      <Modal isOpen={activeModal === "gis"} onClose={closeModal} title="GIS demonstration" maxWidth="2xl" footer={<button type="button" onClick={closeModal} className={secondaryButton}>Close</button>}>
        <div className="space-y-6">
          <section className="space-y-3">
            <div>
              <h4 className="text-sm font-bold text-slate-100">Camera-to-camera travel feasibility</h4>
              <p className="mt-1 text-xs text-slate-400">Tests whether the elapsed time is plausible using the straight-line lower-bound distance. It does not claim a road route.</p>
            </div>
            {geolocated.length < 2 ? (
              <div className="rounded border border-amber-600 bg-amber-950 p-3 text-xs font-semibold text-amber-200">Add verified or approximate GPS metadata to at least two cameras before running this demonstration.</div>
            ) : (
              <div className="grid gap-3 md:grid-cols-3">
                <Field label="From camera"><select aria-label="From camera" className={inputClass} value={fromCameraId} onChange={(event) => setFromCameraId(event.target.value)}>{geolocated.map((camera) => <option key={camera.camera_id} value={camera.camera_id}>{camera.name || camera.camera_id}</option>)}</select></Field>
                <Field label="To camera"><select aria-label="To camera" className={inputClass} value={toCameraId} onChange={(event) => setToCameraId(event.target.value)}>{geolocated.map((camera) => <option key={camera.camera_id} value={camera.camera_id}>{camera.name || camera.camera_id}</option>)}</select></Field>
                <Field label="Elapsed time (minutes)"><input aria-label="Elapsed time in minutes" className={inputClass} value={elapsedMinutes} onChange={(event) => setElapsedMinutes(event.target.value)} /></Field>
                <button type="button" className={primaryButton} onClick={runRouteCheck}>Check feasibility</button>
              </div>
            )}
            {routeError && <div role="alert" className="rounded border border-amber-600 bg-amber-950 p-3 text-xs font-semibold text-amber-200">{routeError}</div>}
            {routeResult && (
              <div className="rounded border border-police-750 bg-police-900 p-3 text-xs text-slate-300">
                <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-bold text-slate-100">{routeResult.from_camera_id} → {routeResult.to_camera_id}</span><span className={`operator-badge rounded px-2 py-1 ${routeResult.feasibility === "FEASIBLE" ? "operator-badge--success" : routeResult.feasibility === "IMPOSSIBLE" ? "operator-badge--danger" : "operator-badge--warning"}`}>{routeResult.feasibility}</span></div>
                <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3"><Metric label="Lower-bound distance" value={`${(routeResult.distance_lower_bound_m / 1000).toFixed(2)} km`} /><Metric label="Minimum speed" value={`${routeResult.minimum_required_speed_kmh.toFixed(1)} km/h`} /><Metric label="Evidence score" value={`${Math.round(routeResult.segment_score * 100)}%`} /></div>
                <p className="mt-3 leading-5">{routeResult.explanation}</p><p className="mt-2 text-[11px] text-amber-300">{routeResult.disclaimer}</p>
              </div>
            )}
          </section>

          <section className="space-y-3 border-t border-police-750 pt-5">
            <div>
              <h4 className="text-sm font-bold text-slate-100">Planning coverage estimate</h4>
              <p className="mt-1 text-xs text-slate-400">Paste an official WGS84 GeoJSON Polygon or MultiPolygon. Circular buffers are a planning approximation, not measured visibility.</p>
            </div>
            <Field label="Area of interest GeoJSON"><textarea aria-label="Area of interest GeoJSON" rows={5} className={inputClass} value={aoiGeoJson} onChange={(event) => setAoiGeoJson(event.target.value)} placeholder={'{"type":"Polygon","coordinates":[[[72.56,23.01],[72.58,23.01],[72.58,23.03],[72.56,23.03],[72.56,23.01]]]}'}/></Field>
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Default radius (metres)"><input aria-label="Default coverage radius" className={inputClass} value={coverageRadius} onChange={(event) => setCoverageRadius(event.target.value)} /></Field>
              <label className="flex items-center gap-2 pb-2 text-xs font-semibold text-slate-200"><input type="checkbox" checked={includeApproximate} onChange={(event) => setIncludeApproximate(event.target.checked)} /> Include approximate coordinates</label>
              <button type="button" className={primaryButton} onClick={runCoverage} disabled={!aoiGeoJson.trim()}>Analyze coverage</button>
            </div>
            {coverageError && <div role="alert" className="rounded border border-amber-600 bg-amber-950 p-3 text-xs font-semibold text-amber-200">{coverageError}</div>}
            {coverageResult && <div className="grid grid-cols-2 gap-2 md:grid-cols-4"><Metric label="Eligible cameras" value={String(coverageResult.eligible_camera_count)} /><Metric label="Coverage estimate" value={`${coverageResult.coverage_percent.toFixed(1)}%`} /><Metric label="Covered area" value={`${(coverageResult.covered_area_m2 / 1_000_000).toFixed(2)} km²`} /><Metric label="Uncovered area" value={`${(coverageResult.uncovered_area_m2 / 1_000_000).toFixed(2)} km²`} warning={coverageResult.uncovered_area_m2 > 0} /></div>}
          </section>
        </div>
      </Modal>
    </>
  );
}
