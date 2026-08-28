from typing import List, Optional
import importlib
from fastapi import APIRouter, Depends, Query, Request, status

try:
    from ..schemas.targets import (
        TargetCreateRequest,
        TargetUpdateRequest,
        TargetResponse,
        TargetListResponse,
        TargetPriorityEnum
    )
    from ..services.target_service import TargetService
    from ..dependencies import get_target_service, get_metrics
    from ..metrics import MetricsCollector
except (ImportError, ValueError):
    tgt_m = importlib.import_module("08_backend.schemas.targets")
    TargetCreateRequest, TargetUpdateRequest, TargetResponse, TargetListResponse, TargetPriorityEnum = (
        tgt_m.TargetCreateRequest, tgt_m.TargetUpdateRequest, tgt_m.TargetResponse, tgt_m.TargetListResponse, tgt_m.TargetPriorityEnum
    )
    TargetService = importlib.import_module("08_backend.services.target_service").TargetService
    dep_m = importlib.import_module("08_backend.dependencies")
    get_target_service, get_metrics = dep_m.get_target_service, dep_m.get_metrics
    MetricsCollector = importlib.import_module("08_backend.metrics").MetricsCollector

# 10_security always via importlib (module name starts with digit)
_sec_m = importlib.import_module("10_security")
Permission = _sec_m.Permission
AuthenticatedPrincipal = _sec_m.AuthenticatedPrincipal
get_audit_logger = _sec_m.get_audit_logger
_s_dep = importlib.import_module("10_security.dependencies")
require_permission = _s_dep.require_permission
validate_csrf_token = _s_dep.validate_csrf_token

router = APIRouter(prefix="/api/v1/targets", tags=["Target Watchlist & Intelligence"])




@router.post("", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def create_target(
    http_request: Request,
    payload: TargetCreateRequest,
    service: TargetService = Depends(get_target_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.TARGET_CREATE)),
    _csrf = Depends(validate_csrf_token),
    audit = Depends(get_audit_logger)
):
    """Add a target vehicle registration to the active police watchlist (SUPERVISOR, ADMIN)."""
    metrics.inc_requests()
    target = service.create_target(payload)
    audit.log_event(
        action="CREATE_TARGET",
        resource_type="target",
        outcome="SUCCESS",
        principal=principal,
        resource_id=target.target_id,
        request_id=http_request.headers.get("X-Request-ID"),
        details={"registration": target.registration, "priority": target.priority.value if hasattr(target.priority, "value") else str(target.priority)},
        fail_closed=True
    )
    return target


@router.get("", response_model=TargetListResponse)
async def list_targets(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    priority: Optional[TargetPriorityEnum] = Query(default=None),
    enabled: Optional[bool] = Query(default=None),
    service: TargetService = Depends(get_target_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.TARGET_READ))
):
    """List registered watchlist targets with priority and status filters."""
    metrics.inc_requests()
    targets = service.list_targets(limit=limit, offset=offset, priority=priority, enabled=enabled)
    return TargetListResponse(items=targets, total=len(targets))


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(
    target_id: str,
    service: TargetService = Depends(get_target_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.TARGET_READ))
):
    """Get target details by watchlist ID."""
    metrics.inc_requests()
    return service.get_target(target_id)


@router.patch("/{target_id}", response_model=TargetResponse)
async def update_target(
    http_request: Request,
    target_id: str,
    payload: TargetUpdateRequest,
    service: TargetService = Depends(get_target_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.TARGET_UPDATE)),
    _csrf = Depends(validate_csrf_token),
    audit = Depends(get_audit_logger)
):
    """Update target priority, status, notes, or expiry (SUPERVISOR, ADMIN)."""
    metrics.inc_requests()
    target = service.update_target(target_id, payload)
    audit.log_event(
        action="UPDATE_TARGET",
        resource_type="target",
        outcome="SUCCESS",
        principal=principal,
        resource_id=target.target_id,
        request_id=http_request.headers.get("X-Request-ID"),
        details={"registration": target.registration},
        fail_closed=True
    )
    return target


@router.delete("/{target_id}", response_model=TargetResponse)
async def disable_target(
    http_request: Request,
    target_id: str,
    service: TargetService = Depends(get_target_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.TARGET_DISABLE)),
    _csrf = Depends(validate_csrf_token),
    audit = Depends(get_audit_logger)
):
    """Disable/archive a target from active watchlist monitoring (SUPERVISOR, ADMIN)."""
    metrics.inc_requests()
    target = service.disable_target(target_id)
    audit.log_event(
        action="DISABLE_TARGET",
        resource_type="target",
        outcome="SUCCESS",
        principal=principal,
        resource_id=target.target_id,
        request_id=http_request.headers.get("X-Request-ID"),
        details={"registration": target.registration},
        fail_closed=True
    )
    return target

