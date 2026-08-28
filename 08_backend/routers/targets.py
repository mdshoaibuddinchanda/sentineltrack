from typing import List, Optional
import importlib
from fastapi import APIRouter, Depends, Query, status

try:
    from ..schemas.targets import (
        TargetCreateRequest,
        TargetUpdateRequest,
        TargetResponse,
        TargetListResponse,
        TargetPriorityEnum
    )
    from ..services.target_service import TargetService
    from ..dependencies import get_target_service, get_metrics, record_audit_event, get_current_user_placeholder
    from ..metrics import MetricsCollector
except (ImportError, ValueError):
    tgt_m = importlib.import_module("08_backend.schemas.targets")
    TargetCreateRequest, TargetUpdateRequest, TargetResponse, TargetListResponse, TargetPriorityEnum = tgt_m.TargetCreateRequest, tgt_m.TargetUpdateRequest, tgt_m.TargetResponse, tgt_m.TargetListResponse, tgt_m.TargetPriorityEnum
    TargetService = importlib.import_module("08_backend.services.target_service").TargetService
    dep_m = importlib.import_module("08_backend.dependencies")
    get_target_service, get_metrics, record_audit_event, get_current_user_placeholder = dep_m.get_target_service, dep_m.get_metrics, dep_m.record_audit_event, dep_m.get_current_user_placeholder
    MetricsCollector = importlib.import_module("08_backend.metrics").MetricsCollector

router = APIRouter(prefix="/api/v1/targets", tags=["Target Watchlist & Intelligence"])


@router.post("", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def create_target(
    request: TargetCreateRequest,
    service: TargetService = Depends(get_target_service),
    metrics: MetricsCollector = Depends(get_metrics),
    current_user: str = Depends(get_current_user_placeholder)
):
    """Add a target vehicle registration to the active police watchlist."""
    metrics.inc_requests()
    target = service.create_target(request)
    record_audit_event(action="CREATE_TARGET", target=target.registration, actor=current_user)
    return target


@router.get("", response_model=TargetListResponse)
async def list_targets(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    priority: Optional[TargetPriorityEnum] = Query(default=None),
    enabled: Optional[bool] = Query(default=None),
    service: TargetService = Depends(get_target_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """List registered watchlist targets with priority and status filters."""
    metrics.inc_requests()
    targets = service.list_targets(limit=limit, offset=offset, priority=priority, enabled=enabled)
    return TargetListResponse(items=targets, total=len(targets))


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(
    target_id: str,
    service: TargetService = Depends(get_target_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Get target details by watchlist ID."""
    metrics.inc_requests()
    return service.get_target(target_id)


@router.patch("/{target_id}", response_model=TargetResponse)
async def update_target(
    target_id: str,
    request: TargetUpdateRequest,
    service: TargetService = Depends(get_target_service),
    metrics: MetricsCollector = Depends(get_metrics),
    current_user: str = Depends(get_current_user_placeholder)
):
    """Update target priority, status, notes, or expiry."""
    metrics.inc_requests()
    target = service.update_target(target_id, request)
    record_audit_event(action="UPDATE_TARGET", target=target.registration, actor=current_user)
    return target


@router.delete("/{target_id}", response_model=TargetResponse)
async def disable_target(
    target_id: str,
    service: TargetService = Depends(get_target_service),
    metrics: MetricsCollector = Depends(get_metrics),
    current_user: str = Depends(get_current_user_placeholder)
):
    """Disable/archive a target from active watchlist monitoring."""
    metrics.inc_requests()
    target = service.disable_target(target_id)
    record_audit_event(action="DISABLE_TARGET", target=target.registration, actor=current_user)
    return target
