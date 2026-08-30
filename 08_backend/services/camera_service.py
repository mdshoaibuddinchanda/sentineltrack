import importlib
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from ..errors import CameraNotFoundError
    from ..schemas.cameras import CameraResponse, CameraHealthResponse
except (ImportError, ValueError):
    CameraNotFoundError = importlib.import_module("08_backend.errors").CameraNotFoundError
    cam_m = importlib.import_module("08_backend.schemas.cameras")
    CameraResponse, CameraHealthResponse = cam_m.CameraResponse, cam_m.CameraHealthResponse


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


def _runtime_stream_status(
    camera_id: str,
    fallback: str,
    *,
    live: bool,
    source_configured: bool,
    runtime_state: Optional[Dict[str, Any]] = None,
) -> str:
    """Prefer current worker state and never call an inactive registry row online."""
    camera_state = runtime_state if runtime_state is not None else _runtime_state(camera_id)
    if camera_state is not None:
        if camera_state.get("connected"):
            return "ONLINE"
        if camera_state.get("degraded"):
            return "OFFLINE"
        return "CONNECTING"

    # A persisted probe status is not a current runtime connection. In
    # particular, test/registry rows often retain ONLINE while live=false.
    if not live or not source_configured:
        return "NOT_CONFIGURED"
    return fallback


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


class CameraService:
    """Service managing camera registry, spatial searches, and camera health metadata."""

    def __init__(self, camera_repo=None):
        self.camera_repo = camera_repo or _get_cam_repo()

    def list_cameras(
        self,
        limit: int = 50,
        offset: int = 0,
        department: Optional[str] = None,
        live: Optional[bool] = None,
        stream_status: Optional[str] = None
    ) -> List[CameraResponse]:
        db = _get_db()
        if not db:
            return []

        conn = db.get_connection()
        query = [
            "SELECT camera_id, name, department, latitude, longitude, azimuth, location_quality, live, stream_status, measured_fps, last_checked, "
            "(COALESCE(rtsp_url, '') <> '' OR COALESCE(hls_url, '') <> '') AS source_configured "
            "FROM cameras WHERE 1=1"
        ]
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

        query.append("ORDER BY camera_id ASC LIMIT %s OFFSET %s;")
        params.extend([limit, offset])

        with conn.cursor() as cur:
            cur.execute(" ".join(query), params)
            rows = cur.fetchall()
            cameras = []
            for r in rows:
                live = bool(r[7])
                source_configured = bool(r[11])
                runtime_state = _runtime_state(r[0])
                runtime_fields = _runtime_fields(runtime_state)
                cameras.append(CameraResponse(
                    camera_id=r[0],
                    name=r[1],
                    department=r[2],
                    latitude=r[3],
                    longitude=r[4],
                    azimuth=r[5],
                    location_quality=r[6] or "VERIFIED",
                    live=live,
                    stream_status=_runtime_stream_status(
                        r[0], r[8] or ("ONLINE" if live else "OFFLINE"),
                        live=live,
                        source_configured=source_configured,
                        runtime_state=runtime_state,
                    ),
                    measured_fps=r[9],
                    last_checked=r[10],
                    source_configured=source_configured,
                    **runtime_fields,
                ))
        conn.close()
        return cameras

    def get_camera_by_id(self, camera_id: str) -> CameraResponse:
        db = _get_db()
        if not db:
            raise CameraNotFoundError(f"Camera '{camera_id}' not found.")

        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT camera_id, name, department, latitude, longitude, azimuth, location_quality, live, stream_status, measured_fps, last_checked, "
                "(COALESCE(rtsp_url, '') <> '' OR COALESCE(hls_url, '') <> '') AS source_configured "
                "FROM cameras WHERE camera_id = %s;",
                (camera_id,)
            )
            r = cur.fetchone()
        conn.close()

        if not r:
            raise CameraNotFoundError(f"Camera '{camera_id}' not found.")

        live = bool(r[7])
        source_configured = bool(r[11])
        runtime_state = _runtime_state(r[0])
        return CameraResponse(
            camera_id=r[0],
            name=r[1],
            department=r[2],
            latitude=r[3],
            longitude=r[4],
            azimuth=r[5],
            location_quality=r[6] or "VERIFIED",
            live=live,
            stream_status=_runtime_stream_status(
                r[0], r[8] or ("ONLINE" if live else "OFFLINE"),
                live=live,
                source_configured=source_configured,
                runtime_state=runtime_state,
            ),
            measured_fps=r[9],
            last_checked=r[10],
            source_configured=source_configured,
            **_runtime_fields(runtime_state),
        )

    def get_nearby_cameras(self, latitude: float, longitude: float, radius_m: float = 5000.0) -> List[CameraResponse]:
        if not self.camera_repo:
            return []
        nearby = self.camera_repo.get_nearby_cameras(latitude, longitude, radius_m)
        db = _get_db()
        results = []
        for c in nearby:
            record = db.get_camera(c.camera_id) if db else None
            live = bool(record.get("live")) if record else False
            source_configured = bool(record and (record.get("rtsp_url") or record.get("hls_url")))
            runtime_state = _runtime_state(c.camera_id)
            runtime_fields = _runtime_fields(runtime_state)
            results.append(CameraResponse(
                camera_id=c.camera_id,
                name=c.name,
                department=(record.get("department") if record else (c.metadata.get("department") if c.metadata else None)),
                latitude=c.latitude,
                longitude=c.longitude,
                azimuth=c.azimuth,
                location_quality=c.location_quality.value if hasattr(c.location_quality, "value") else str(c.location_quality),
                live=live,
                stream_status=_runtime_stream_status(
                    c.camera_id,
                    (record.get("stream_status") if record else "UNKNOWN"),
                    live=live,
                    source_configured=source_configured,
                    runtime_state=runtime_state,
                ),
                measured_fps=record.get("measured_fps") if record else None,
                last_checked=record.get("last_checked") if record else None,
                source_configured=source_configured,
                **runtime_fields,
            ))
        return results

    def get_camera_health(self, camera_id: str) -> CameraHealthResponse:
        cam = self.get_camera_by_id(camera_id)
        runtime_state = _runtime_state(camera_id)
        runtime_fields = _runtime_fields(runtime_state)
        return CameraHealthResponse(
            camera_id=cam.camera_id,
            stream_status=cam.stream_status,
            # No synthetic latency: this is populated only when a real probe
            # records it in the registry.
            first_frame_latency_ms=None,
            last_pts_ms=runtime_state.get("last_pts_ms") if runtime_state else None,
            last_checked=(
                datetime.fromtimestamp(time.time(), timezone.utc)
                if runtime_state and runtime_state.get("last_frame_s_ago") is not None
                else cam.last_checked
            ),
            source_configured=cam.source_configured,
            connected=bool(runtime_state and runtime_state.get("connected")),
            **runtime_fields,
        )
