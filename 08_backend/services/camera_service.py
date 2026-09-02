from __future__ import annotations

import csv
from collections import Counter
import importlib
import io
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from psycopg import rows
from pydantic import ValidationError

try:
    from ..errors import CameraNotFoundError, DuplicateCameraError, InvalidCameraRegistryError, InvalidQueryParameterError
    from ..schemas.cameras import (
        CameraBulkImportRequest,
        CameraBulkImportResponse,
        CameraGapAnalysisResponse,
        CameraHealthResponse,
        CameraImportItemResult,
        CameraImportMode,
        CameraMutationResponse,
        CameraRegistryInput,
        CameraResponse,
        CameraUpdateRequest,
        CoverageAnalysisRequest,
        CoverageAnalysisResponse,
    )
except (ImportError, ValueError):
    err_m = importlib.import_module("08_backend.errors")
    CameraNotFoundError = err_m.CameraNotFoundError
    DuplicateCameraError = err_m.DuplicateCameraError
    InvalidCameraRegistryError = err_m.InvalidCameraRegistryError
    InvalidQueryParameterError = err_m.InvalidQueryParameterError
    cam_m = importlib.import_module("08_backend.schemas.cameras")
    CameraBulkImportRequest = cam_m.CameraBulkImportRequest
    CameraBulkImportResponse = cam_m.CameraBulkImportResponse
    CameraGapAnalysisResponse = cam_m.CameraGapAnalysisResponse
    CameraHealthResponse = cam_m.CameraHealthResponse
    CameraImportItemResult = cam_m.CameraImportItemResult
    CameraImportMode = cam_m.CameraImportMode
    CameraMutationResponse = cam_m.CameraMutationResponse
    CameraRegistryInput = cam_m.CameraRegistryInput
    CameraResponse = cam_m.CameraResponse
    CameraUpdateRequest = cam_m.CameraUpdateRequest
    CoverageAnalysisRequest = cam_m.CoverageAnalysisRequest
    CoverageAnalysisResponse = cam_m.CoverageAnalysisResponse


CAMERA_COLUMNS = """
    camera_id, name, department, latitude, longitude, azimuth, location_quality,
    organization, source_system, external_id, onboarding_method,
    coordinate_source, coordinate_accuracy_m, coverage_radius_m, field_of_view_degrees,
    live, stream_status, measured_fps, first_frame_latency_ms, last_pts_ms,
    last_checked, rtsp_url, hls_url, webrtc_url, raw_metadata, updated_at
"""


def _get_db():
    try:
        return importlib.import_module("00_foundation.registry.database")
    except Exception:
        return None


def _get_cam_repo():
    try:
        cam_repo_mod = importlib.import_module("07_route_engine.camera_repository")
        return cam_repo_mod.PostgresCameraRepository()
    except Exception:
        return None


def _runtime_state(camera_id: str) -> Optional[Dict[str, Any]]:
    """Return process-local worker state, if this camera is actively supervised."""
    try:
        lifecycle = importlib.import_module("08_backend.lifecycle")
        supervisor = lifecycle.get_stream_supervisor()
        if supervisor is None:
            return None
        return supervisor.get_status().get("cameras", {}).get(camera_id)
    except Exception:
        return None


def _source_issue(camera_id: str) -> tuple[Optional[str], Optional[str]]:
    """Return the startup source blocker for a camera, without secrets."""
    try:
        lifecycle = importlib.import_module("08_backend.lifecycle")
        diagnostics = lifecycle.get_stream_ingestion_diagnostics()
        blocked = {str(value) for value in diagnostics.get("blocked_camera_ids", [])}
        if str(camera_id) not in blocked:
            return None, None
        return (
            str(diagnostics.get("code") or "SOURCE_UNAVAILABLE"),
            str(diagnostics.get("message") or "The camera source is unavailable."),
        )
    except Exception:
        return None, None


def _display_name(name: Optional[str], raw_metadata: Any) -> Optional[str]:
    if isinstance(raw_metadata, dict):
        location = raw_metadata.get("location")
        if isinstance(location, str) and location.strip():
            return location.strip()
    return name


def _location_quality(value: Optional[str], latitude: Any, longitude: Any) -> str:
    if latitude is None or longitude is None:
        return "UNKNOWN"
    return value or "UNKNOWN"


def _runtime_stream_status(
    camera_id: str,
    fallback: str,
    *,
    live: bool,
    source_configured: bool,
    runtime_state: Optional[Dict[str, Any]] = None,
    issue_code: Optional[str] = None,
) -> str:
    """Prefer current worker state and never call an inactive registry row online."""
    camera_state = runtime_state if runtime_state is not None else _runtime_state(camera_id)
    if camera_state is not None:
        if camera_state.get("connected"):
            return "ONLINE"
        if camera_state.get("degraded"):
            return "OFFLINE"
        return "CONNECTING"

    if issue_code in {"AUTH_REQUIRED", "AUTH_FAILED"}:
        return "AUTH_REQUIRED"
    if issue_code:
        return "OFFLINE"
    if not live or not source_configured:
        return "NOT_CONFIGURED"
    return "UNKNOWN"


def _runtime_fields(runtime_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not runtime_state:
        return {
            "frames_decoded": 0,
            "frames_sampled": 0,
            "reconnects": 0,
            "last_frame_s_ago": None,
        }
    return {
        "frames_decoded": int(runtime_state.get("frames_decoded", 0)),
        "frames_sampled": int(runtime_state.get("frames_sampled", 0)),
        "reconnects": int(runtime_state.get("reconnects", 0)),
        "last_frame_s_ago": runtime_state.get("last_frame_s_ago"),
    }


def _registry_metadata(raw_metadata: Any) -> Dict[str, Any]:
    if not isinstance(raw_metadata, dict):
        return {}
    value = raw_metadata.get("registry_metadata")
    return value if isinstance(value, dict) else {}


def _csv_cell(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


class CameraService:
    """Camera registry, controlled onboarding, health, and GIS coverage service."""

    def __init__(self, camera_repo=None):
        self.camera_repo = camera_repo or _get_cam_repo()

    @staticmethod
    def _require_db():
        db = _get_db()
        if not db:
            raise RuntimeError("Camera registry database is unavailable.")
        return db

    def _row_to_response(self, record: Dict[str, Any]) -> CameraResponse:
        camera_id = str(record["camera_id"])
        live = True if record.get("live") is None else bool(record.get("live"))
        source_configured = bool(record.get("rtsp_url") or record.get("hls_url"))
        runtime_state = _runtime_state(camera_id)
        issue_code, issue_message = _source_issue(camera_id)
        if runtime_state and runtime_state.get("connection_issue_code"):
            issue_code = str(runtime_state["connection_issue_code"])
            issue_message = str(runtime_state.get("connection_issue_message") or "") or None
        return CameraResponse(
            camera_id=camera_id,
            name=_display_name(record.get("name"), record.get("raw_metadata")),
            department=record.get("department"),
            latitude=record.get("latitude"),
            longitude=record.get("longitude"),
            azimuth=record.get("azimuth"),
            location_quality=_location_quality(
                record.get("location_quality"), record.get("latitude"), record.get("longitude")
            ),
            organization=record.get("organization"),
            source_system=record.get("source_system"),
            external_id=record.get("external_id"),
            onboarding_method=record.get("onboarding_method"),
            coordinate_source=record.get("coordinate_source"),
            coordinate_accuracy_m=record.get("coordinate_accuracy_m"),
            coverage_radius_m=record.get("coverage_radius_m"),
            field_of_view_degrees=record.get("field_of_view_degrees"),
            live=live,
            stream_status=_runtime_stream_status(
                camera_id,
                record.get("stream_status") or ("ONLINE" if live else "OFFLINE"),
                live=live,
                source_configured=source_configured,
                runtime_state=runtime_state,
                issue_code=issue_code,
            ),
            measured_fps=record.get("measured_fps"),
            last_checked=record.get("last_checked"),
            source_configured=source_configured,
            connection_issue_code=issue_code,
            connection_issue_message=issue_message,
            metadata=_registry_metadata(record.get("raw_metadata")),
            **_runtime_fields(runtime_state),
        )

    def list_cameras(
        self,
        limit: int = 50,
        offset: int = 0,
        department: Optional[str] = None,
        live: Optional[bool] = None,
        stream_status: Optional[str] = None,
    ) -> List[CameraResponse]:
        db = self._require_db()
        query = [f"SELECT {CAMERA_COLUMNS} FROM cameras WHERE 1=1"]
        params: List[Any] = []
        if department:
            query.append("AND department = %s")
            params.append(department)
        if live is not None:
            query.append("AND live = %s")
            params.append(live)
        if stream_status:
            query.append("AND stream_status = %s")
            params.append(stream_status)
        query.append("ORDER BY camera_id ASC LIMIT %s OFFSET %s")
        params.extend([limit, offset])
        with db.get_connection() as conn:
            with conn.cursor(row_factory=rows.dict_row) as cur:
                cur.execute(" ".join(query), params)
                records = cur.fetchall()
        return [self._row_to_response(record) for record in records]

    def count_cameras(
        self,
        department: Optional[str] = None,
        live: Optional[bool] = None,
        stream_status: Optional[str] = None,
    ) -> int:
        db = self._require_db()
        query = ["SELECT COUNT(*) FROM cameras WHERE 1=1"]
        params: List[Any] = []
        if department:
            query.append("AND department = %s")
            params.append(department)
        if live is not None:
            query.append("AND live = %s")
            params.append(live)
        if stream_status:
            query.append("AND stream_status = %s")
            params.append(stream_status)
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(" ".join(query), params)
                return int(cur.fetchone()[0])

    def _get_record(self, camera_id: str, *, for_update: bool = False, cursor=None) -> Dict[str, Any]:
        query = f"SELECT {CAMERA_COLUMNS} FROM cameras WHERE camera_id = %s"
        if for_update:
            query += " FOR UPDATE"
        if cursor is not None:
            cursor.execute(query, (camera_id,))
            record = cursor.fetchone()
        else:
            db = self._require_db()
            with db.get_connection() as conn:
                with conn.cursor(row_factory=rows.dict_row) as cur:
                    cur.execute(query, (camera_id,))
                    record = cur.fetchone()
        if not record:
            raise CameraNotFoundError(f"Camera '{camera_id}' not found.")
        return dict(record)

    def get_camera_by_id(self, camera_id: str) -> CameraResponse:
        return self._row_to_response(self._get_record(camera_id))

    @staticmethod
    def _write_camera(cur, payload: CameraRegistryInput, onboarding_method: str) -> None:
        metadata = {
            "registry_metadata": payload.metadata,
            "registry_provenance": {
                "onboarding_method": onboarding_method,
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        }
        cur.execute(
            """
            INSERT INTO cameras (
                camera_id, name, department, organization, source_system, external_id,
                onboarding_method, latitude, longitude, location, azimuth, location_quality,
                coordinate_source, coordinate_accuracy_m, coverage_radius_m,
                field_of_view_degrees, rtsp_url, hls_url, webrtc_url, live,
                stream_status, raw_metadata, updated_at
            ) VALUES (
                %(camera_id)s, %(name)s, %(department)s, %(organization)s,
                %(source_system)s, %(external_id)s, %(onboarding_method)s,
                %(latitude)s, %(longitude)s,
                CASE WHEN %(latitude)s::double precision IS NOT NULL AND %(longitude)s::double precision IS NOT NULL
                     THEN ST_SetSRID(ST_MakePoint(%(longitude)s::double precision, %(latitude)s::double precision), 4326)::geography
                     ELSE NULL END,
                %(azimuth)s, %(location_quality)s, %(coordinate_source)s,
                %(coordinate_accuracy_m)s, %(coverage_radius_m)s, %(field_of_view_degrees)s,
                %(rtsp_url)s, %(hls_url)s, %(webrtc_url)s, %(live)s,
                'UNKNOWN', %(raw_metadata)s::jsonb, NOW()
            )
            ON CONFLICT (camera_id) DO UPDATE SET
                name = EXCLUDED.name,
                department = EXCLUDED.department,
                organization = EXCLUDED.organization,
                source_system = EXCLUDED.source_system,
                external_id = EXCLUDED.external_id,
                onboarding_method = EXCLUDED.onboarding_method,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                location = EXCLUDED.location,
                azimuth = EXCLUDED.azimuth,
                location_quality = EXCLUDED.location_quality,
                coordinate_source = EXCLUDED.coordinate_source,
                coordinate_accuracy_m = EXCLUDED.coordinate_accuracy_m,
                coverage_radius_m = EXCLUDED.coverage_radius_m,
                field_of_view_degrees = EXCLUDED.field_of_view_degrees,
                rtsp_url = EXCLUDED.rtsp_url,
                hls_url = EXCLUDED.hls_url,
                webrtc_url = EXCLUDED.webrtc_url,
                live = EXCLUDED.live,
                raw_metadata = COALESCE(cameras.raw_metadata, '{}'::jsonb) || EXCLUDED.raw_metadata,
                updated_at = NOW()
            """,
            {
                **payload.model_dump(mode="json"),
                "location_quality": payload.location_quality.value,
                "onboarding_method": onboarding_method,
                "raw_metadata": json.dumps(metadata),
            },
        )

    @staticmethod
    def _worker_sync(camera_id: str) -> str:
        try:
            lifecycle = importlib.import_module("08_backend.lifecycle")
            return str(lifecycle.sync_camera_worker(camera_id))
        except Exception:
            return "RESTART_REQUIRED"

    def create_camera(
        self,
        payload: CameraRegistryInput,
        before_commit: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> CameraMutationResponse:
        db = self._require_db()
        try:
            with db.get_connection() as conn:
                with conn.cursor(row_factory=rows.dict_row) as cur:
                    cur.execute("SELECT camera_id FROM cameras WHERE camera_id = %s FOR UPDATE", (payload.camera_id,))
                    if cur.fetchone():
                        raise DuplicateCameraError(f"Camera '{payload.camera_id}' is already registered.")
                    self._write_camera(cur, payload, "MANUAL")
                    if before_commit:
                        before_commit({"created": True, "camera_ids": [payload.camera_id]})
        except DuplicateCameraError:
            raise
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505":
                raise DuplicateCameraError("The camera source identity is already registered.") from exc
            raise
        if self.camera_repo:
            self.camera_repo.refresh_cache()
        worker_status = self._worker_sync(payload.camera_id)
        return CameraMutationResponse(
            camera=self.get_camera_by_id(payload.camera_id),
            created=True,
            worker_status=worker_status,
        )

    def update_camera(
        self,
        camera_id: str,
        patch: CameraUpdateRequest,
        before_commit: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> CameraMutationResponse:
        db = self._require_db()
        try:
            with db.get_connection() as conn:
                with conn.cursor(row_factory=rows.dict_row) as cur:
                    existing = self._get_record(camera_id, for_update=True, cursor=cur)
                    merged = {
                        "camera_id": camera_id,
                        "name": existing.get("name"),
                        "department": existing.get("department"),
                        "organization": existing.get("organization"),
                        "source_system": existing.get("source_system") or "MANUAL",
                        "external_id": existing.get("external_id") or camera_id,
                        "latitude": existing.get("latitude"),
                        "longitude": existing.get("longitude"),
                        "azimuth": existing.get("azimuth"),
                        "location_quality": existing.get("location_quality") or "UNKNOWN",
                        "coordinate_source": existing.get("coordinate_source"),
                        "coordinate_accuracy_m": existing.get("coordinate_accuracy_m"),
                        "coverage_radius_m": existing.get("coverage_radius_m"),
                        "field_of_view_degrees": existing.get("field_of_view_degrees"),
                        "rtsp_url": existing.get("rtsp_url"),
                        "hls_url": existing.get("hls_url"),
                        "webrtc_url": existing.get("webrtc_url"),
                        "live": True if existing.get("live") is None else bool(existing.get("live")),
                        "metadata": _registry_metadata(existing.get("raw_metadata")),
                    }
                    merged.update(patch.model_dump(exclude_unset=True, mode="json"))
                    payload = CameraRegistryInput.model_validate(merged)
                    self._write_camera(cur, payload, "MANUAL_UPDATE")
                    if before_commit:
                        before_commit({"created": False, "camera_ids": [camera_id]})
        except ValidationError as exc:
            raise InvalidCameraRegistryError(
                "The camera update would create an invalid registry record.",
                details={
                    "validation_errors": exc.errors(
                        include_input=False,
                        include_url=False,
                        include_context=False,
                    )
                },
            ) from exc
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505":
                raise DuplicateCameraError("The camera source identity is already registered.") from exc
            raise
        if self.camera_repo:
            self.camera_repo.refresh_cache()
        worker_relevant_fields = {"rtsp_url", "hls_url", "webrtc_url", "live"}
        worker_status = (
            self._worker_sync(camera_id)
            if worker_relevant_fields.intersection(patch.model_fields_set)
            else "UNCHANGED"
        )
        return CameraMutationResponse(
            camera=self.get_camera_by_id(camera_id),
            created=False,
            worker_status=worker_status,
        )

    def bulk_import(
        self,
        request: CameraBulkImportRequest,
        before_commit: Optional[Callable[[Dict[str, Any]], None]] = None,
        onboarding_method: str = "BULK_API",
    ) -> CameraBulkImportResponse:
        db = self._require_db()
        id_counts = Counter(camera.camera_id for camera in request.cameras)
        duplicate_rows = {
            row_number
            for row_number, camera in enumerate(request.cameras, start=1)
            if id_counts[camera.camera_id] > 1
        }

        with db.get_connection() as conn:
            with conn.cursor(row_factory=rows.dict_row) as cur:
                cur.execute(
                    "SELECT camera_id FROM cameras WHERE camera_id = ANY(%s)",
                    ([camera.camera_id for camera in request.cameras],),
                )
                existing_ids = {str(row["camera_id"]) for row in cur.fetchall()}

        results: List[CameraImportItemResult] = []
        changes: List[tuple[CameraRegistryInput, bool, int]] = []
        for row_number, camera in enumerate(request.cameras, start=1):
            if row_number in duplicate_rows:
                results.append(CameraImportItemResult(
                    row=row_number,
                    camera_id=camera.camera_id,
                    status="SKIPPED",
                    message="Duplicate camera_id in this import batch.",
                ))
                continue
            exists = camera.camera_id in existing_ids
            if exists and request.mode == CameraImportMode.CREATE_ONLY:
                results.append(CameraImportItemResult(
                    row=row_number,
                    camera_id=camera.camera_id,
                    status="SKIPPED",
                    message="Camera already exists; choose UPSERT to update it.",
                ))
                continue
            changes.append((camera, exists, row_number))
            results.append(CameraImportItemResult(
                row=row_number,
                camera_id=camera.camera_id,
                status="WOULD_UPDATE" if exists else "WOULD_CREATE",
                message="Validated; no database change made." if request.dry_run else "Pending import.",
            ))

        created = sum(1 for _, exists, _ in changes if not exists)
        updated = sum(1 for _, exists, _ in changes if exists)
        worker_started = 0
        restart_required = 0
        if not request.dry_run and changes:
            try:
                with db.get_connection() as conn:
                    with conn.cursor() as cur:
                        for camera, _, _ in changes:
                            self._write_camera(cur, camera, onboarding_method)
                        if before_commit:
                            before_commit({
                                "created": created,
                                "updated": updated,
                                "camera_ids": [camera.camera_id for camera, _, _ in changes],
                            })
            except Exception as exc:
                if getattr(exc, "sqlstate", None) == "23505":
                    raise DuplicateCameraError("A camera source identity conflicts with an existing registry row.") from exc
                raise
            if self.camera_repo:
                self.camera_repo.refresh_cache()
            status_by_id = {camera.camera_id: self._worker_sync(camera.camera_id) for camera, _, _ in changes}
            worker_started = sum(1 for status in status_by_id.values() if status == "STARTED")
            restart_required = sum(1 for status in status_by_id.values() if status == "RESTART_REQUIRED")
            changed_rows = {row_number for _, _, row_number in changes}
            for item in results:
                if item.row in changed_rows:
                    item.status = "UPDATED" if item.camera_id in existing_ids else "CREATED"
                    item.message = f"Imported; worker status: {status_by_id[item.camera_id]}."

        return CameraBulkImportResponse(
            dry_run=request.dry_run,
            received=len(request.cameras),
            valid=len(request.cameras) - len(duplicate_rows),
            created=created if not request.dry_run else 0,
            updated=updated if not request.dry_run else 0,
            skipped=len(results) - len(changes),
            worker_started=worker_started,
            worker_restart_required=restart_required,
            items=results,
        )

    def get_nearby_cameras(self, latitude: float, longitude: float, radius_m: float = 5000.0) -> List[CameraResponse]:
        if not self.camera_repo:
            return []
        return [
            self.get_camera_by_id(camera.camera_id)
            for camera in self.camera_repo.get_nearby_cameras(latitude, longitude, radius_m)
        ]

    def get_camera_health(self, camera_id: str) -> CameraHealthResponse:
        record = self._get_record(camera_id)
        cam = self._row_to_response(record)
        runtime_state = _runtime_state(camera_id)
        issue_code, issue_message = _source_issue(camera_id)
        if runtime_state and runtime_state.get("connection_issue_code"):
            issue_code = str(runtime_state["connection_issue_code"])
            issue_message = str(runtime_state.get("connection_issue_message") or "") or None
        return CameraHealthResponse(
            camera_id=cam.camera_id,
            stream_status=cam.stream_status,
            first_frame_latency_ms=record.get("first_frame_latency_ms"),
            last_pts_ms=runtime_state.get("last_pts_ms") if runtime_state else record.get("last_pts_ms"),
            last_checked=(
                datetime.fromtimestamp(time.time(), timezone.utc)
                if runtime_state and runtime_state.get("last_frame_s_ago") is not None
                else cam.last_checked
            ),
            source_configured=cam.source_configured,
            connected=bool(runtime_state and runtime_state.get("connected")),
            connection_issue_code=issue_code,
            connection_issue_message=issue_message,
            **_runtime_fields(runtime_state),
        )

    @staticmethod
    def _group_counts(cur, column: str) -> Dict[str, int]:
        if column not in {"source_system", "organization", "department"}:
            raise ValueError("Unsupported camera grouping column.")
        cur.execute(
            f"SELECT COALESCE(NULLIF(BTRIM({column}), ''), 'UNSPECIFIED') AS key, COUNT(*) AS count "
            f"FROM cameras GROUP BY key ORDER BY count DESC, key ASC"
        )
        return {str(row[0]): int(row[1]) for row in cur.fetchall()}

    def build_gap_analysis(self, isolation_radius_m: float = 5000.0) -> CameraGapAnalysisResponse:
        db = self._require_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*),
                        COUNT(*) FILTER (WHERE latitude IS NOT NULL AND longitude IS NOT NULL),
                        COUNT(*) FILTER (WHERE location_quality = 'VERIFIED' AND location IS NOT NULL),
                        COUNT(*) FILTER (WHERE location_quality = 'APPROXIMATE' AND location IS NOT NULL),
                        COUNT(*) FILTER (WHERE location_quality = 'UNKNOWN' OR location IS NULL),
                        COUNT(*) FILTER (WHERE location IS NULL),
                        COUNT(*) FILTER (WHERE location IS NOT NULL AND NULLIF(BTRIM(coordinate_source), '') IS NULL),
                        COUNT(*) FILTER (WHERE NULLIF(BTRIM(department), '') IS NULL),
                        COUNT(*) FILTER (WHERE NULLIF(BTRIM(organization), '') IS NULL),
                        COUNT(*) FILTER (WHERE azimuth IS NULL),
                        COUNT(*) FILTER (WHERE COALESCE(rtsp_url, '') = '' AND COALESCE(hls_url, '') = ''),
                        COUNT(*) FILTER (WHERE live IS TRUE)
                    FROM cameras
                    """
                )
                counts = cur.fetchone()
                source_systems = self._group_counts(cur, "source_system")
                organizations = self._group_counts(cur, "organization")
                departments = self._group_counts(cur, "department")
                cur.execute(
                    """
                    SELECT c.camera_id
                    FROM cameras c
                    WHERE c.location IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM cameras other
                          WHERE other.camera_id <> c.camera_id
                            AND other.location IS NOT NULL
                            AND ST_DWithin(c.location, other.location, %s)
                      )
                    ORDER BY c.camera_id
                    LIMIT 500
                    """,
                    (isolation_radius_m,),
                )
                isolated = [str(row[0]) for row in cur.fetchall()]
        return CameraGapAnalysisResponse(
            generated_at_utc=datetime.now(timezone.utc),
            total_cameras=int(counts[0]),
            geolocated_cameras=int(counts[1]),
            verified_coordinates=int(counts[2]),
            approximate_coordinates=int(counts[3]),
            unknown_coordinates=int(counts[4]),
            missing_coordinates=int(counts[5]),
            missing_coordinate_source=int(counts[6]),
            missing_department=int(counts[7]),
            missing_organization=int(counts[8]),
            missing_azimuth=int(counts[9]),
            missing_stream_source=int(counts[10]),
            enabled_cameras=int(counts[11]),
            source_systems=source_systems,
            organizations=organizations,
            departments=departments,
            isolated_camera_ids=isolated,
            isolation_radius_m=isolation_radius_m,
            limitations=[
                "Missing coordinates are reported, never inferred from camera names.",
                "Isolation uses straight-line distance and is not a road-network or line-of-sight result.",
                "Coverage requires an operator-supplied area of interest and surveyed camera geometry.",
            ],
        )

    def build_gap_analysis_csv(self, isolation_radius_m: float = 5000.0) -> str:
        report = self.build_gap_analysis(isolation_radius_m)
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("report_type", "SentinelTrack camera registry gap analysis"))
        for key, value in report.model_dump(mode="json").items():
            if isinstance(value, dict):
                for group_key, count in value.items():
                    writer.writerow((_csv_cell(f"{key}.{group_key}"), count))
            elif isinstance(value, list):
                writer.writerow((key, _csv_cell(" | ".join(str(item) for item in value))))
            else:
                writer.writerow((key, _csv_cell(value)))
        return output.getvalue()

    def export_geojson(self, limit: int = 10000) -> Dict[str, Any]:
        db = self._require_db()
        with db.get_connection() as conn:
            with conn.cursor(row_factory=rows.dict_row) as cur:
                cur.execute(
                    f"SELECT {CAMERA_COLUMNS} FROM cameras WHERE location IS NOT NULL ORDER BY camera_id LIMIT %s",
                    (limit,),
                )
                records = cur.fetchall()
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": record["camera_id"],
                    "geometry": {
                        "type": "Point",
                        "coordinates": [record["longitude"], record["latitude"]],
                    },
                    "properties": {
                        "camera_id": record["camera_id"],
                        "name": _display_name(record.get("name"), record.get("raw_metadata")),
                        "department": record.get("department"),
                        "organization": record.get("organization"),
                        "source_system": record.get("source_system"),
                        "location_quality": record.get("location_quality") or "UNKNOWN",
                        "coordinate_source": record.get("coordinate_source"),
                        "azimuth": record.get("azimuth"),
                        "coverage_radius_m": record.get("coverage_radius_m"),
                    },
                }
                for record in records
            ],
            "properties": {
                "coordinate_reference_system": "OGC:CRS84",
                "axis_order": "longitude, latitude",
                "returned": len(records),
                "limit": limit,
            },
        }

    def analyze_coverage(self, request: CoverageAnalysisRequest) -> CoverageAnalysisResponse:
        db = self._require_db()
        geometry_json = json.dumps(request.area_of_interest)
        try:
            with db.get_connection() as conn:
                with conn.cursor(row_factory=rows.dict_row) as cur:
                    cur.execute(
                        """
                        WITH input AS (
                            SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) AS geom
                        ),
                        aoi AS (
                            SELECT ST_CollectionExtract(ST_MakeValid(geom), 3) AS geom FROM input
                        ),
                        eligible AS (
                            SELECT location, COALESCE(coverage_radius_m, %s) AS radius_m
                            FROM cameras
                            WHERE location IS NOT NULL
                              AND (location_quality = 'VERIFIED'
                                   OR (%s AND location_quality = 'APPROXIMATE'))
                        ),
                        buffered AS (
                            SELECT ST_UnaryUnion(ST_Collect(ST_Buffer(location, radius_m)::geometry)) AS geom,
                                   COUNT(*) AS camera_count
                            FROM eligible
                        ),
                        clipped AS (
                            SELECT
                                aoi.geom AS aoi_geom,
                                CASE WHEN buffered.geom IS NULL
                                     THEN ST_GeomFromText('POLYGON EMPTY', 4326)
                                     ELSE ST_Intersection(aoi.geom, buffered.geom) END AS covered_geom,
                                buffered.camera_count
                            FROM aoi CROSS JOIN buffered
                        )
                        SELECT
                            ST_IsEmpty(aoi_geom) AS empty_aoi,
                            camera_count,
                            ST_Area(aoi_geom::geography) AS aoi_m2,
                            ST_Area(covered_geom::geography) AS covered_m2,
                            ST_AsGeoJSON(aoi_geom)::jsonb AS aoi_geojson,
                            ST_AsGeoJSON(covered_geom)::jsonb AS covered_geojson,
                            ST_AsGeoJSON(ST_Difference(aoi_geom, covered_geom))::jsonb AS uncovered_geojson
                        FROM clipped
                        """,
                        (
                            geometry_json,
                            request.default_coverage_radius_m,
                            request.include_approximate,
                        ),
                    )
                    result = cur.fetchone()
        except Exception as exc:
            raise InvalidQueryParameterError(
                "The area of interest could not be evaluated as valid WGS84 GeoJSON.",
                details={"reason": type(exc).__name__},
            ) from exc
        if not result or result["empty_aoi"] or float(result["aoi_m2"] or 0.0) <= 0.0:
            raise InvalidQueryParameterError("The area of interest must contain a non-empty polygon.")

        aoi_m2 = float(result["aoi_m2"])
        covered_m2 = min(aoi_m2, max(0.0, float(result["covered_m2"] or 0.0)))
        uncovered_m2 = max(0.0, aoi_m2 - covered_m2)
        return CoverageAnalysisResponse(
            generated_at_utc=datetime.now(timezone.utc),
            eligible_camera_count=int(result["camera_count"] or 0),
            area_of_interest_m2=round(aoi_m2, 2),
            covered_area_m2=round(covered_m2, 2),
            uncovered_area_m2=round(uncovered_m2, 2),
            coverage_percent=round(covered_m2 / aoi_m2 * 100.0, 2),
            default_coverage_radius_m=request.default_coverage_radius_m,
            include_approximate=request.include_approximate,
            coverage_model="PLANNING_BUFFER_APPROXIMATION",
            geojson={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": result["aoi_geojson"], "properties": {"layer": "AREA_OF_INTEREST"}},
                    {"type": "Feature", "geometry": result["covered_geojson"], "properties": {"layer": "ESTIMATED_COVERAGE"}},
                    {"type": "Feature", "geometry": result["uncovered_geojson"], "properties": {"layer": "ESTIMATED_GAP"}},
                ],
            },
            limitations=[
                "Circular buffers are planning approximations, not optical line-of-sight guarantees.",
                "Buildings, terrain, lens parameters, occlusion, and camera health are not modeled.",
                "Only verified coordinates are used unless include_approximate is explicitly enabled.",
            ],
        )
