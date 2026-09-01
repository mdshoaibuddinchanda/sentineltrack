import asyncio
import time
from typing import AsyncGenerator, List, Optional
import importlib
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from fastapi.responses import StreamingResponse

try:
    from ..schemas.cameras import CameraResponse, CameraListResponse, CameraHealthResponse
    from ..services.camera_service import CameraService
    from ..dependencies import get_camera_service, get_metrics
    from ..metrics import MetricsCollector
except (ImportError, ValueError):
    cam_m = importlib.import_module("08_backend.schemas.cameras")
    CameraResponse, CameraListResponse, CameraHealthResponse = cam_m.CameraResponse, cam_m.CameraListResponse, cam_m.CameraHealthResponse
    CameraService = importlib.import_module("08_backend.services.camera_service").CameraService
    dep_m = importlib.import_module("08_backend.dependencies")
    get_camera_service, get_metrics = dep_m.get_camera_service, dep_m.get_metrics
    MetricsCollector = importlib.import_module("08_backend.metrics").MetricsCollector

# 10_security always via importlib (module name starts with digit)
_sec_m = importlib.import_module("10_security")
Permission = _sec_m.Permission
AuthenticatedPrincipal = _sec_m.AuthenticatedPrincipal
require_permission = importlib.import_module("10_security.dependencies").require_permission


router = APIRouter(
    prefix="/api/v1/cameras",
    tags=["Camera Registry & PostGIS"],
    dependencies=[Depends(require_permission(Permission.CAMERA_READ))]
)


@router.get("", response_model=CameraListResponse)
async def list_cameras(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    department: Optional[str] = Query(default=None),
    live: Optional[bool] = Query(default=None),
    stream_status: Optional[str] = Query(default=None),
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """List surveyed cameras with optional spatial and departmental filters."""
    metrics.inc_requests()
    cameras = service.list_cameras(
        limit=limit,
        offset=offset,
        department=department,
        live=live,
        stream_status=stream_status
    )
    return CameraListResponse(items=cameras, total=len(cameras))


@router.get("/nearby", response_model=List[CameraResponse])
async def search_nearby_cameras_by_coordinates(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude in WGS84 EPSG:4326"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude in WGS84 EPSG:4326"),
    radius_m: float = Query(default=5000.0, ge=100.0, le=50000.0, description="Search radius in meters"),
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Find cameras within a geographic radius using PostGIS ST_DWithin."""
    metrics.inc_requests()
    return service.get_nearby_cameras(latitude=lat, longitude=lon, radius_m=radius_m)


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera_detail(
    camera_id: str,
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Get metadata for a specific camera (credentials/passwords sanitized)."""
    metrics.inc_requests()
    return service.get_camera_by_id(camera_id)


@router.get("/{camera_id}/health", response_model=CameraHealthResponse)
async def get_camera_health(
    camera_id: str,
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Get real-time stream status and connectivity health for a camera."""
    metrics.inc_requests()
    return service.get_camera_health(camera_id)


@router.get("/{camera_id}/preview", response_class=Response)
async def get_camera_preview(
    camera_id: str,
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics),
):
    """Return the latest decoded JPEG snapshot for human camera verification."""
    service.get_camera_by_id(camera_id)
    lifecycle = importlib.import_module("08_backend.lifecycle")
    supervisor = lifecycle.get_stream_supervisor()
    preview = supervisor.get_preview(camera_id) if supervisor else None
    metrics.inc_requests()
    if preview is None:
        raise HTTPException(status_code=404, detail="No decoded frame is available for this camera yet.")
    return Response(
        content=preview,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.get("/{camera_id}/live")
async def get_camera_live_stream(
    camera_id: str,
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics),
):
    """Relay a continuous authenticated MJPEG stream from decoded worker frames.

    The browser never receives the upstream RTSP/HLS URL.  Frames are read
    from the process-local worker and encoded only for this live viewer.  A
    stream is opened only when a fresh decoded frame is available.
    """
    service.get_camera_by_id(camera_id)
    lifecycle = importlib.import_module("08_backend.lifecycle")
    supervisor = lifecycle.get_stream_supervisor()
    if supervisor is None:
        raise HTTPException(status_code=503, detail="Live camera ingestion is not running.")

    first_snapshot = supervisor.get_live_snapshot(camera_id)
    if first_snapshot is None:
        raise HTTPException(status_code=404, detail="No fresh decoded frame is available for this camera.")

    metrics.inc_requests()

    async def frame_stream() -> AsyncGenerator[bytes, None]:
        # Keep API-only workers lightweight. OpenCV is loaded only when an
        # authorized operator actually consumes a live camera response.
        import cv2

        last_frame_time = 0.0
        stale_started_at: Optional[float] = None
        try:
            while True:
                snapshot = supervisor.get_live_snapshot(camera_id)
                if snapshot is None:
                    if stale_started_at is None:
                        stale_started_at = time.monotonic()
                    # Keep a short reconnect window for upstream jitter, then
                    # close so the browser can reconnect and show a truthful
                    # unavailable state.
                    if time.monotonic() - stale_started_at >= 8.0:
                        break
                    await asyncio.sleep(0.1)
                    continue

                stale_started_at = None
                frame, frame_time = snapshot
                if frame_time <= last_frame_time:
                    await asyncio.sleep(0.05)
                    continue

                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if not ok:
                    await asyncio.sleep(0.1)
                    continue

                payload = encoded.tobytes()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(payload)}\r\n".encode("ascii")
                    + b"Cache-Control: no-store, max-age=0\r\n\r\n"
                    + payload
                    + b"\r\n"
                )
                last_frame_time = frame_time
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            # A normal browser navigation/tab close cancels the generator.
            return

    return StreamingResponse(
        frame_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{camera_id}/nearby", response_model=List[CameraResponse])
async def get_nearby_cameras_for_camera(
    camera_id: str,
    radius_m: float = Query(default=5000.0, ge=100.0, le=50000.0),
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Find neighboring cameras relative to a specific camera location."""
    metrics.inc_requests()
    cam = service.get_camera_by_id(camera_id)
    if cam.latitude is None or cam.longitude is None:
        return []
    return service.get_nearby_cameras(latitude=cam.latitude, longitude=cam.longitude, radius_m=radius_m)
