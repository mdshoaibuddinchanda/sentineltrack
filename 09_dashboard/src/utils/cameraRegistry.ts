import type { CameraRegistryInput, LocationQuality } from "../types/api";

export const CAMERA_CSV_TEMPLATE = [
  "camera_id,name,department,organization,source_system,external_id,latitude,longitude,location_quality,coordinate_source,azimuth,coordinate_accuracy_m,coverage_radius_m,field_of_view_degrees,rtsp_url,hls_url,webrtc_url,live",
  "cam-example-01,Example Junction,Traffic Police,Example Organization,CSV_IMPORT,external-01,23.0225,72.5714,VERIFIED,Official survey 2026,90,5,100,70,rtsp://camera.example/stream,,,true",
].join("\r\n");

const SUPPORTED_HEADERS = new Set([
  "camera_id",
  "name",
  "department",
  "organization",
  "source_system",
  "external_id",
  "latitude",
  "longitude",
  "azimuth",
  "location_quality",
  "coordinate_source",
  "coordinate_accuracy_m",
  "coverage_radius_m",
  "field_of_view_degrees",
  "rtsp_url",
  "hls_url",
  "webrtc_url",
  "whep_url",
  "live",
]);

function parseCsvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
      continue;
    }

    if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field.trim());
      field = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && text[index + 1] === "\n") index += 1;
      row.push(field.trim());
      field = "";
      if (row.some((value) => value.length > 0)) rows.push(row);
      row = [];
    } else {
      field += char;
    }
  }

  if (quoted) throw new Error("The CSV contains an unclosed quoted value.");
  row.push(field.trim());
  if (row.some((value) => value.length > 0)) rows.push(row);
  return rows;
}

function optional(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

function numberValue(value: string | undefined, label: string, rowNumber: number): number | undefined {
  const raw = optional(value);
  if (raw === undefined) return undefined;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) throw new Error(`Row ${rowNumber}: ${label} must be a number.`);
  return parsed;
}

function booleanValue(value: string | undefined, rowNumber: number): boolean {
  const raw = optional(value)?.toLowerCase();
  if (raw === undefined) return true;
  if (["true", "1", "yes", "y"].includes(raw)) return true;
  if (["false", "0", "no", "n"].includes(raw)) return false;
  throw new Error(`Row ${rowNumber}: live must be true or false.`);
}

function locationQuality(value: string | undefined, rowNumber: number): LocationQuality {
  const normalized = (optional(value) || "UNKNOWN").toUpperCase();
  if (normalized === "VERIFIED" || normalized === "APPROXIMATE" || normalized === "UNKNOWN") {
    return normalized;
  }
  throw new Error(`Row ${rowNumber}: location_quality must be VERIFIED, APPROXIMATE, or UNKNOWN.`);
}

/** Parse a bounded, normalized camera CSV before the server performs authoritative validation. */
export function parseCameraCsv(text: string): CameraRegistryInput[] {
  if (!text.trim()) throw new Error("The selected CSV file is empty.");
  const rows = parseCsvRows(text);
  if (rows.length < 2) throw new Error("The CSV must contain a header and at least one camera row.");

  const headers = rows[0].map((header, index) =>
    (index === 0 ? header.replace(/^\uFEFF/, "") : header).trim().toLowerCase(),
  );
  if (!headers.includes("camera_id")) throw new Error("The CSV is missing the required camera_id header.");
  const duplicateHeaders = headers.filter((header, index) => headers.indexOf(header) !== index);
  if (duplicateHeaders.length > 0) throw new Error(`Duplicate CSV header: ${duplicateHeaders[0]}.`);
  const unsupported = headers.filter((header) => !SUPPORTED_HEADERS.has(header));
  if (unsupported.length > 0) throw new Error(`Unsupported CSV header: ${unsupported[0]}.`);
  if (rows.length - 1 > 500) throw new Error("A camera import is limited to 500 records.");

  const seen = new Set<string>();
  return rows.slice(1).map((values, rowIndex) => {
    const rowNumber = rowIndex + 2;
    if (values.length > headers.length) throw new Error(`Row ${rowNumber}: too many columns.`);
    const record = Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]));
    const cameraId = optional(record.camera_id);
    if (!cameraId) throw new Error(`Row ${rowNumber}: camera_id is required.`);
    if (seen.has(cameraId)) throw new Error(`Row ${rowNumber}: duplicate camera_id '${cameraId}'.`);
    seen.add(cameraId);

    const latitude = numberValue(record.latitude, "latitude", rowNumber);
    const longitude = numberValue(record.longitude, "longitude", rowNumber);
    if ((latitude === undefined) !== (longitude === undefined)) {
      throw new Error(`Row ${rowNumber}: latitude and longitude must be supplied together.`);
    }

    return {
      camera_id: cameraId,
      name: optional(record.name),
      department: optional(record.department),
      organization: optional(record.organization),
      source_system: optional(record.source_system) || "CSV_IMPORT",
      external_id: optional(record.external_id) || cameraId,
      latitude,
      longitude,
      azimuth: numberValue(record.azimuth, "azimuth", rowNumber),
      location_quality: locationQuality(record.location_quality, rowNumber),
      coordinate_source: optional(record.coordinate_source),
      coordinate_accuracy_m: numberValue(record.coordinate_accuracy_m, "coordinate_accuracy_m", rowNumber),
      coverage_radius_m: numberValue(record.coverage_radius_m, "coverage_radius_m", rowNumber),
      field_of_view_degrees: numberValue(record.field_of_view_degrees, "field_of_view_degrees", rowNumber),
      rtsp_url: optional(record.rtsp_url),
      hls_url: optional(record.hls_url),
      webrtc_url: optional(record.webrtc_url) || optional(record.whep_url),
      live: booleanValue(record.live, rowNumber),
      metadata: {},
    };
  });
}

export function downloadCameraCsvTemplate(): void {
  const blob = new Blob([CAMERA_CSV_TEMPLATE], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "sentineltrack_camera_import_template.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
