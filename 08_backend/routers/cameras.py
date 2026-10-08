import asyncio
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional
import importlib
from fastapi import APIRouter, Depends, Query, Response, HTTPException, Request, status
from fastapi.responses import StreamingResponse

try:
    from ..schemas.cameras import (
        CameraResponse, CameraListResponse, CameraHealthResponse,
        CameraRegistryInput, CameraUpdateRequest, CameraMutationResponse,
        CameraBulkImportRequest, CameraBulkImportResponse,
        CameraGapAnalysisResponse, CoverageAnalysisRequest, CoverageAnalysisResponse,
        VMSConnectorListResponse, VMSConnectorSyncRequest,
    )
    from ..services.camera_service import CameraService
    from ..dependencies import get_camera_service, get_metrics, get_vms_service
    from ..metrics import MetricsCollector
except (ImportError, ValueError):
    cam_m = importlib.import_module("08_backend.schemas.cameras")
    CameraResponse, CameraListResponse, CameraHealthResponse = cam_m.CameraResponse, cam_m.CameraListResponse, cam_m.CameraHealthResponse
    CameraRegistryInput, CameraUpdateRequest, CameraMutationResponse = cam_m.CameraRegistryInput, cam_m.CameraUpdateRequest, cam_m.CameraMutationResponse
    CameraBulkImportRequest, CameraBulkImportResponse = cam_m.CameraBulkImportRequest, cam_m.CameraBulkImportResponse
    CameraGapAnalysisResponse, CoverageAnalysisRequest, CoverageAnalysisResponse = cam_m.CameraGapAnalysisResponse, cam_m.CoverageAnalysisRequest, cam_m.CoverageAnalysisResponse
    VMSConnectorListResponse, VMSConnectorSyncRequest = cam_m.VMSConnectorListResponse, cam_m.VMSConnectorSyncRequest
    CameraService = importlib.import_module("08_backend.services.camera_service").CameraService
    dep_m = importlib.import_module("08_backend.dependencies")
    get_camera_service, get_metrics, get_vms_service = dep_m.get_camera_service, dep_m.get_metrics, dep_m.get_vms_service
    MetricsCollector = importlib.import_module("08_backend.metrics").MetricsCollector

# 10_security always via importlib (module name starts with digit)
_sec_m = importlib.import_module("10_security")
Permission = _sec_m.Permission
AuthenticatedPrincipal = _sec_m.AuthenticatedPrincipal
get_audit_logger = _sec_m.get_audit_logger
require_permission = importlib.import_module("10_security.dependencies").require_permission
validate_csrf_token = importlib.import_module("10_security.dependencies").validate_csrf_token


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
    total = service.count_cameras(department=department, live=live, stream_status=stream_status)
    return CameraListResponse(items=cameras, total=total)


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


@router.post("", response_model=CameraMutationResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(
    http_request: Request,
    payload: CameraRegistryInput,
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.CAMERA_MANAGE)),
    _csrf=Depends(validate_csrf_token),
    audit=Depends(get_audit_logger),
):
    """Manually register one camera without storing credentials in the registry."""
    metrics.inc_requests()

    def audit_before_commit(details):
        audit.log_event(
            action="CREATE_CAMERA",
            resource_type="camera",
            outcome="SUCCESS",
            principal=principal,
            resource_id=payload.camera_id,
            request_id=http_request.headers.get("X-Request-ID"),
            details={
                "source_system": payload.source_system,
                "organization": payload.organization,
                "has_coordinates": payload.latitude is not None,
                "location_quality": payload.location_quality.value,
            },
            fail_closed=True,
        )

    return service.create_camera(payload, before_commit=audit_before_commit)


@router.post("/bulk", response_model=CameraBulkImportResponse)
async def bulk_import_cameras(
    http_request: Request,
    payload: CameraBulkImportRequest,
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.CAMERA_MANAGE)),
    _csrf=Depends(validate_csrf_token),
    audit=Depends(get_audit_logger),
):
    """Validate or atomically import up to 500 normalized camera records."""
    metrics.inc_requests()

    def audit_before_commit(details):
        camera_ids = details.get("camera_ids", [])
        audit.log_event(
            action="BULK_IMPORT_CAMERAS",
            resource_type="camera_registry",
            outcome="SUCCESS",
            principal=principal,
            resource_id=f"batch:{len(camera_ids)}",
            request_id=http_request.headers.get("X-Request-ID"),
            details={
                "mode": payload.mode.value,
                "created": details.get("created", 0),
                "updated": details.get("updated", 0),
                "camera_ids_sample": camera_ids[:25],
                "camera_ids_truncated": len(camera_ids) > 25,
            },
            fail_closed=True,
        )

    return service.bulk_import(
        payload,
        before_commit=None if payload.dry_run else audit_before_commit,
    )


@router.get("/gap-analysis", response_model=CameraGapAnalysisResponse)
async def get_camera_gap_analysis(
    isolation_radius_m: float = Query(default=5000.0, ge=100.0, le=50000.0),
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics),
):
    """Report registry metadata, geolocation, source, and spatial-isolation gaps."""
    metrics.inc_requests()
    return service.build_gap_analysis(isolation_radius_m)


@router.get("/gap-analysis.csv")
async def export_camera_gap_analysis(
    http_request: Request,
    isolation_radius_m: float = Query(default=5000.0, ge=100.0, le=50000.0),
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.CAMERA_READ)),
    audit=Depends(get_audit_logger),
):
    """Export the same gap evidence as a spreadsheet-safe CSV report."""
    metrics.inc_requests()
    report = service.build_gap_analysis_csv(isolation_radius_m)
    audit.log_event(
        action="EXPORT_CAMERA_GAP_ANALYSIS",
        resource_type="camera_registry_report",
        outcome="SUCCESS",
        principal=principal,
        request_id=http_request.headers.get("X-Request-ID"),
        details={"format": "csv", "isolation_radius_m": isolation_radius_m},
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Response(
        content=report,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="sentineltrack_camera_gap_analysis_{stamp}.csv"',
            "Cache-Control": "no-store, max-age=0",
        },
    )


@router.get("/export.geojson")
async def export_camera_geojson(
    http_request: Request,
    limit: int = Query(default=10000, ge=1, le=100000),
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.CAMERA_READ)),
    audit=Depends(get_audit_logger),
):
    """Export geolocated cameras as OGC:CRS84 GeoJSON without stream URLs."""
    metrics.inc_requests()
    result = service.export_geojson(limit)
    audit.log_event(
        action="EXPORT_CAMERA_GEOJSON",
        resource_type="camera_registry_report",
        outcome="SUCCESS",
        principal=principal,
        request_id=http_request.headers.get("X-Request-ID"),
        details={"format": "geojson", "returned": len(result.get("features", []))},
    )
    return result


@router.post("/coverage-analysis", response_model=CoverageAnalysisResponse)
async def analyze_camera_coverage(
    http_request: Request,
    payload: CoverageAnalysisRequest,
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.CAMERA_READ)),
    _csrf=Depends(validate_csrf_token),
    audit=Depends(get_audit_logger),
):
    """Estimate planning coverage for an operator-supplied WGS84 area of interest."""
    metrics.inc_requests()
    result = service.analyze_coverage(payload)
    audit.log_event(
        action="ANALYZE_CAMERA_COVERAGE",
        resource_type="camera_coverage",
        outcome="SUCCESS",
        principal=principal,
        request_id=http_request.headers.get("X-Request-ID"),
        details={
            "eligible_camera_count": result.eligible_camera_count,
            "coverage_percent": result.coverage_percent,
            "include_approximate": payload.include_approximate,
        },
    )
    return result


@router.get("/connectors", response_model=VMSConnectorListResponse)
async def list_vms_connectors(
    metrics: MetricsCollector = Depends(get_metrics),
    vms_service=Depends(get_vms_service),
):
    """List secret-free readiness for configured heterogeneous VMS adapters."""
    metrics.inc_requests()
    return vms_service.list_connectors()


@router.post("/connectors/{connector_id}/sync", response_model=CameraBulkImportResponse)
async def sync_vms_connector(
    http_request: Request,
    connector_id: str,
    payload: VMSConnectorSyncRequest,
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.CAMERA_MANAGE)),
    _csrf=Depends(validate_csrf_token),
    audit=Depends(get_audit_logger),
    vms_service=Depends(get_vms_service),
):
    """Validate or import one trusted, file-configured VMS source."""
    metrics.inc_requests()

    def audit_before_commit(details):
        camera_ids = details.get("camera_ids", [])
        audit.log_event(
            action="SYNC_VMS_CONNECTOR",
            resource_type="camera_registry",
            outcome="SUCCESS",
            principal=principal,
            resource_id=connector_id,
            request_id=http_request.headers.get("X-Request-ID"),
            details={
                "created": details.get("created", 0),
                "updated": details.get("updated", 0),
                "camera_count": len(camera_ids),
                "camera_ids_sample": camera_ids[:25],
            },
            fail_closed=True,
        )

    result = vms_service.sync(
        connector_id,
        payload,
        before_commit=None if payload.dry_run else audit_before_commit,
    )
    if payload.dry_run:
        audit.log_event(
            action="VALIDATE_VMS_CONNECTOR",
            resource_type="camera_registry",
            outcome="SUCCESS",
            principal=principal,
            resource_id=connector_id,
            request_id=http_request.headers.get("X-Request-ID"),
            details={"discovered": result.received, "mode": payload.mode.value},
        )
    return result


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera_detail(
    camera_id: str,
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Get metadata for a specific camera (credentials/passwords sanitized)."""
    metrics.inc_requests()
    return service.get_camera_by_id(camera_id)


@router.patch("/{camera_id}/registry", response_model=CameraMutationResponse)
async def update_camera_registry(
    http_request: Request,
    camera_id: str,
    payload: CameraUpdateRequest,
    service: CameraService = Depends(get_camera_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.CAMERA_MANAGE)),
    _csrf=Depends(validate_csrf_token),
    audit=Depends(get_audit_logger),
):
    """Update camera metadata or source configuration with fail-closed audit."""
    metrics.inc_requests()

    def audit_before_commit(details):
        audit.log_event(
            action="UPDATE_CAMERA",
            resource_type="camera",
            outcome="SUCCESS",
            principal=principal,
            resource_id=camera_id,
            request_id=http_request.headers.get("X-Request-ID"),
            details={"changed_fields": sorted(payload.model_fields_set)},
            fail_closed=True,
        )

    return service.update_camera(camera_id, payload, before_commit=audit_before_commit)


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
