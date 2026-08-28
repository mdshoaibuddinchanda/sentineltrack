from datetime import datetime
from typing import Any, Dict, Optional
import importlib
from fastapi import APIRouter, Depends, Query, Response

try:
    from ..schemas.routes import RouteResponse, RouteSummaryResponse, GeoJSONFeatureCollection
    from ..services.route_service import RouteService
    from ..dependencies import get_route_service, get_metrics, record_audit_event, get_current_user_placeholder
    from ..metrics import MetricsCollector
except (ImportError, ValueError):
    rt_m = importlib.import_module("08_backend.schemas.routes")
    RouteResponse, RouteSummaryResponse, GeoJSONFeatureCollection = rt_m.RouteResponse, rt_m.RouteSummaryResponse, rt_m.GeoJSONFeatureCollection
    RouteService = importlib.import_module("08_backend.services.route_service").RouteService
    dep_m = importlib.import_module("08_backend.dependencies")
    get_route_service, get_metrics, record_audit_event, get_current_user_placeholder = dep_m.get_route_service, dep_m.get_metrics, dep_m.record_audit_event, dep_m.get_current_user_placeholder
    MetricsCollector = importlib.import_module("08_backend.metrics").MetricsCollector

router = APIRouter(prefix="/api/v1/routes", tags=["Route Engine & Trajectory GIS"])


@router.get("/{registration}", response_model=RouteResponse)
async def get_target_route(
    registration: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    min_match_score: float = Query(default=0.60, ge=0.0, le=1.0),
    persist: bool = Query(default=True, description="Whether to persist this trajectory run in PostgreSQL"),
    service: RouteService = Depends(get_route_service),
    metrics: MetricsCollector = Depends(get_metrics),
    current_user: str = Depends(get_current_user_placeholder)
):
    """
    Reconstructs the multi-camera spatio-temporal trajectory for a target vehicle registration.
    Applies kinematic feasibility verification, ambiguity detection, and conflict identification.
    """
    metrics.inc_requests()
    record_audit_event(action="QUERY_ROUTE", target=registration, actor=current_user)
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
    registration: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    min_match_score: float = Query(default=0.60, ge=0.0, le=1.0),
    service: RouteService = Depends(get_route_service),
    metrics: MetricsCollector = Depends(get_metrics),
    current_user: str = Depends(get_current_user_placeholder)
) -> Dict[str, Any]:
    """
    Exports the target vehicle trajectory as an RFC-7946 compliant GeoJSON FeatureCollection.
    Features include Point camera observations and LineString trajectory segments.
    """
    metrics.inc_requests()
    record_audit_event(action="QUERY_ROUTE_GEOJSON", target=registration, actor=current_user)
    return service.get_route_geojson(
        registration=registration,
        start_time_utc=start_time,
        end_time_utc=end_time,
        min_match_score=min_match_score
    )


@router.get("/{registration}/summary", response_model=RouteSummaryResponse)
async def get_target_route_summary(
    registration: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    min_match_score: float = Query(default=0.60, ge=0.0, le=1.0),
    service: RouteService = Depends(get_route_service),
    metrics: MetricsCollector = Depends(get_metrics),
    current_user: str = Depends(get_current_user_placeholder)
):
    """Returns high-level investigative summary for rapid operator triage."""
    metrics.inc_requests()
    record_audit_event(action="QUERY_ROUTE_SUMMARY", target=registration, actor=current_user)
    return service.get_route_summary(
        registration=registration,
        start_time_utc=start_time,
        end_time_utc=end_time,
        min_match_score=min_match_score
    )
