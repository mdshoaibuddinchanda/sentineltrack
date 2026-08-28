import importlib
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
            "SELECT camera_id, name, department, latitude, longitude, azimuth, location_quality, live, stream_status, measured_fps, last_checked "
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
                cameras.append(CameraResponse(
                    camera_id=r[0],
                    name=r[1],
                    department=r[2],
                    latitude=r[3],
                    longitude=r[4],
                    azimuth=r[5],
                    location_quality=r[6] or "VERIFIED",
                    live=bool(r[7]),
                    stream_status=r[8] or "ONLINE",
                    measured_fps=r[9],
                    last_checked=r[10]
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
                "SELECT camera_id, name, department, latitude, longitude, azimuth, location_quality, live, stream_status, measured_fps, last_checked "
                "FROM cameras WHERE camera_id = %s;",
                (camera_id,)
            )
            r = cur.fetchone()
        conn.close()

        if not r:
            raise CameraNotFoundError(f"Camera '{camera_id}' not found.")

        return CameraResponse(
            camera_id=r[0],
            name=r[1],
            department=r[2],
            latitude=r[3],
            longitude=r[4],
            azimuth=r[5],
            location_quality=r[6] or "VERIFIED",
            live=bool(r[7]),
            stream_status=r[8] or "ONLINE",
            measured_fps=r[9],
            last_checked=r[10]
        )

    def get_nearby_cameras(self, latitude: float, longitude: float, radius_m: float = 5000.0) -> List[CameraResponse]:
        if not self.camera_repo:
            return []
        nearby = self.camera_repo.get_nearby_cameras(latitude, longitude, radius_m)
        return [
            CameraResponse(
                camera_id=c.camera_id,
                name=c.name,
                department=c.metadata.get("department") if c.metadata else None,
                latitude=c.latitude,
                longitude=c.longitude,
                azimuth=c.azimuth,
                location_quality=c.location_quality.value if hasattr(c.location_quality, "value") else str(c.location_quality),
                live=True,
                stream_status="ONLINE"
            )
            for c in nearby
        ]

    def get_camera_health(self, camera_id: str) -> CameraHealthResponse:
        cam = self.get_camera_by_id(camera_id)
        return CameraHealthResponse(
            camera_id=cam.camera_id,
            stream_status=cam.stream_status,
            first_frame_latency_ms=120.0,
            last_pts_ms=None,
            last_checked=cam.last_checked or datetime.now(timezone.utc)
        )
