from typing import List, Optional
import importlib
from fastapi import APIRouter, Depends, Query

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

router = APIRouter(prefix="/api/v1/cameras", tags=["Camera Registry & PostGIS"])


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
