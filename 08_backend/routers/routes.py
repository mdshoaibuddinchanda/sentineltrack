from datetime import datetime, timezone
import re
from typing import Any, Dict, Optional
import importlib
from fastapi import APIRouter, Depends, Query, Request, Response

try:
    from ..schemas.routes import RouteResponse, RouteSummaryResponse, GeoJSONFeatureCollection, CameraPairFeasibilityRequest, CameraPairFeasibilityResponse
    from ..services.route_service import RouteService
    from ..dependencies import get_route_service, get_metrics
    from ..metrics import MetricsCollector
except (ImportError, ValueError):
    rt_m = importlib.import_module("08_backend.schemas.routes")
    RouteResponse, RouteSummaryResponse, GeoJSONFeatureCollection = rt_m.RouteResponse, rt_m.RouteSummaryResponse, rt_m.GeoJSONFeatureCollection
    CameraPairFeasibilityRequest, CameraPairFeasibilityResponse = rt_m.CameraPairFeasibilityRequest, rt_m.CameraPairFeasibilityResponse
    RouteService = importlib.import_module("08_backend.services.route_service").RouteService
    dep_m = importlib.import_module("08_backend.dependencies")
    get_route_service, get_metrics = dep_m.get_route_service, dep_m.get_metrics
    MetricsCollector = importlib.import_module("08_backend.metrics").MetricsCollector

# 10_security always via importlib (module name starts with digit — can't use from X import in try)
_sec_m = importlib.import_module("10_security")
Permission = _sec_m.Permission
AuthenticatedPrincipal = _sec_m.AuthenticatedPrincipal
get_audit_logger = _sec_m.get_audit_logger
require_permission = importlib.import_module("10_security.dependencies").require_permission

router = APIRouter(prefix="/api/v1/routes", tags=["Route Engine & Trajectory GIS"])


@router.post("/feasibility-check", response_model=CameraPairFeasibilityResponse)
async def check_camera_pair_feasibility(
    http_request: Request,
    payload: CameraPairFeasibilityRequest,
    service: RouteService = Depends(get_route_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ROUTE_READ)),
    audit=Depends(get_audit_logger),
):
    """Demonstrate P7 lower-bound movement feasibility without creating sightings."""
    metrics.inc_requests()
    result = service.evaluate_camera_pair(
        payload.from_camera_id,
        payload.to_camera_id,
        payload.elapsed_seconds,
    )
    audit.log_event(
        action="CHECK_CAMERA_PAIR_FEASIBILITY",
        resource_type="route_demo",
        outcome="SUCCESS",
        principal=principal,
        resource_id=f"{payload.from_camera_id}:{payload.to_camera_id}",
        request_id=http_request.headers.get("X-Request-ID"),
        details={
            "elapsed_seconds": payload.elapsed_seconds,
            "feasibility": result.feasibility,
        },
    )
    return result




@router.get("/{registration}", response_model=RouteResponse)
async def get_target_route(
    http_request: Request,
    registration: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    min_match_score: float = Query(default=0.60, ge=0.0, le=1.0),
    persist: bool = Query(default=False, description="Whether to persist this trajectory run in PostgreSQL"),
    service: RouteService = Depends(get_route_service),

    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ROUTE_READ)),
    audit = Depends(get_audit_logger)
):
    """
    Reconstructs the multi-camera spatio-temporal trajectory for a target vehicle registration.
    Applies kinematic feasibility verification, ambiguity detection, and conflict identification.
    """
    metrics.inc_requests()
    audit.log_event(
        action="QUERY_ROUTE",
        resource_type="route",
        outcome="SUCCESS",
        principal=principal,
        resource_id=registration,
        request_id=http_request.headers.get("X-Request-ID"),
        details={"min_match_score": min_match_score}
    )
    route = service.build_target_trajectory(
        registration=registration,
        start_time_utc=start_time,
        end_time_utc=end_time,
        min_match_score=min_match_score,
        persist=persist
    )
    metrics.inc_analytics(routes=1)
    return route


@router.get("/{registration}/geojson")
async def get_target_route_geojson(
    http_request: Request,
    registration: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    min_match_score: float = Query(default=0.60, ge=0.0, le=1.0),
    service: RouteService = Depends(get_route_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ROUTE_READ)),
    audit = Depends(get_audit_logger)
) -> Dict[str, Any]:
    """
    Exports the target vehicle trajectory as an RFC-7946 compliant GeoJSON FeatureCollection.
    Features include Point camera observations and LineString trajectory segments.
    """
    metrics.inc_requests()
    audit.log_event(
        action="QUERY_ROUTE_GEOJSON",
        resource_type="route",
        outcome="SUCCESS",
        principal=principal,
        resource_id=registration,
        request_id=http_request.headers.get("X-Request-ID")
    )
    return service.get_route_geojson(
        registration=registration,
        start_time_utc=start_time,
        end_time_utc=end_time,
        min_match_score=min_match_score
    )


@router.get("/{registration}/summary", response_model=RouteSummaryResponse)
async def get_target_route_summary(
    http_request: Request,
    registration: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    min_match_score: float = Query(default=0.60, ge=0.0, le=1.0),
    service: RouteService = Depends(get_route_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ROUTE_READ)),
    audit = Depends(get_audit_logger)
):
    """Returns high-level investigative summary for rapid operator triage."""
    metrics.inc_requests()
    audit.log_event(
        action="QUERY_ROUTE_SUMMARY",
        resource_type="route",
        outcome="SUCCESS",
        principal=principal,
        resource_id=registration,
        request_id=http_request.headers.get("X-Request-ID")
    )
    return service.get_route_summary(
        registration=registration,
        start_time_utc=start_time,
        end_time_utc=end_time,
        min_match_score=min_match_score
    )


@router.get("/{registration}/report.csv")
async def export_target_route_report(
    http_request: Request,
    registration: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    min_match_score: float = Query(default=0.60, ge=0.0, le=1.0),
    service: RouteService = Depends(get_route_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ROUTE_READ)),
    audit = Depends(get_audit_logger),
):
    """Download a timestamped CSV report from the same evidence as the route UI."""
    metrics.inc_requests()
    report = service.build_route_csv_report(
        registration=registration,
        start_time_utc=start_time,
        end_time_utc=end_time,
        min_match_score=min_match_score,
    )
    audit.log_event(
        action="EXPORT_ROUTE_REPORT",
        resource_type="route_report",
        outcome="SUCCESS",
        principal=principal,
        resource_id=registration,
        request_id=http_request.headers.get("X-Request-ID"),
        details={"format": "csv", "min_match_score": min_match_score},
    )
    safe_registration = re.sub(r"[^A-Z0-9_-]", "", registration.upper()) or "vehicle"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Response(
        content=report,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="sentineltrack_{safe_registration}_{stamp}.csv"',
            "Cache-Control": "no-store, max-age=0",
        },
    )

