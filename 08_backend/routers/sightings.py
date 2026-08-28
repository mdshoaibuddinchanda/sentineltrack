from datetime import datetime
from typing import List, Optional
import importlib
from fastapi import APIRouter, Depends, Query

try:
    from ..schemas.sightings import SightingResponse, SightingListResponse, VehicleHistoryResponse
    from ..services.sighting_service import SightingService
    from ..dependencies import get_sighting_service, get_metrics, record_audit_event, get_current_user_placeholder
    from ..metrics import MetricsCollector
except (ImportError, ValueError):
    sight_m = importlib.import_module("08_backend.schemas.sightings")
    SightingResponse, SightingListResponse, VehicleHistoryResponse = sight_m.SightingResponse, sight_m.SightingListResponse, sight_m.VehicleHistoryResponse
    SightingService = importlib.import_module("08_backend.services.sighting_service").SightingService
    dep_m = importlib.import_module("08_backend.dependencies")
    get_sighting_service, get_metrics, record_audit_event, get_current_user_placeholder = dep_m.get_sighting_service, dep_m.get_metrics, dep_m.record_audit_event, dep_m.get_current_user_placeholder
    MetricsCollector = importlib.import_module("08_backend.metrics").MetricsCollector

router = APIRouter(tags=["Sightings & Historical Search"])


@router.get("/api/v1/sightings", response_model=SightingListResponse)
async def list_sightings(
    registration: Optional[str] = Query(default=None, description="Wildcard or exact registration pattern e.g. GJ01*"),
    camera_id: Optional[str] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: SightingService = Depends(get_sighting_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Query vehicle observations across cameras with temporal, camera, and match score filters."""
    metrics.inc_requests()
    sightings = service.query_sightings(
        registration_pattern=registration,
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
        min_score=min_score,
        limit=limit,
        offset=offset
    )
    return SightingListResponse(items=sightings, total=len(sightings))


@router.get("/api/v1/vehicles/{registration}/history", response_model=VehicleHistoryResponse)
async def get_vehicle_history(
    registration: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    service: SightingService = Depends(get_sighting_service),
    metrics: MetricsCollector = Depends(get_metrics),
    current_user: str = Depends(get_current_user_placeholder)
):
    """Retrieve full chronological observation history for a specific vehicle registration."""
    metrics.inc_requests()
    record_audit_event(action="SEARCH_HISTORY", target=registration, actor=current_user)
    return service.get_vehicle_history(
        registration=registration,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )
