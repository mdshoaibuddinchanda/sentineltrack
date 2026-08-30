from typing import List, Optional
import importlib
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

try:
    from ..schemas.alerts import AlertResponse, AlertListResponse, AlertAckRequest, AlertAckResponse
    from ..services.alert_service import AlertService
    from ..dependencies import get_alert_service, get_metrics
    from ..metrics import MetricsCollector
except (ImportError, ValueError):
    alt_m = importlib.import_module("08_backend.schemas.alerts")
    AlertResponse, AlertListResponse, AlertAckRequest, AlertAckResponse = (
        alt_m.AlertResponse, alt_m.AlertListResponse, alt_m.AlertAckRequest, alt_m.AlertAckResponse
    )
    AlertService = importlib.import_module("08_backend.services.alert_service").AlertService
    dep_m = importlib.import_module("08_backend.dependencies")
    get_alert_service, get_metrics = dep_m.get_alert_service, dep_m.get_metrics
    MetricsCollector = importlib.import_module("08_backend.metrics").MetricsCollector

# 10_security always via importlib (module name starts with digit)
_sec_m = importlib.import_module("10_security")
Permission = _sec_m.Permission
AuthenticatedPrincipal = _sec_m.AuthenticatedPrincipal
get_audit_logger = _sec_m.get_audit_logger
_s_dep = importlib.import_module("10_security.dependencies")
require_permission = _s_dep.require_permission
validate_csrf_token = _s_dep.validate_csrf_token


router = APIRouter(prefix="/api/v1/alerts", tags=["Target Alerts & Incident Response"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    unacknowledged: bool = Query(default=False, description="Filter for unacknowledged alerts only"),
    camera_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: AlertService = Depends(get_alert_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ALERT_READ))
):
    """List real-time target match alerts with acknowledgement and camera filters."""
    metrics.inc_requests()
    alerts = service.query_alerts(
        unacknowledged_only=unacknowledged,
        camera_id=camera_id,
        limit=limit,
        offset=offset
    )
    # Counts describe the complete filtered database result, not just the
    # current page. This prevents a page of 50 historical rows from being
    # presented as the system-wide alert count.
    total = service.count_alerts(camera_id=camera_id)
    unack_count = service.count_alerts(unacknowledged_only=True, camera_id=camera_id)
    return AlertListResponse(items=alerts, total=total, unacknowledged_count=unack_count)


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert_detail(
    alert_id: str,
    service: AlertService = Depends(get_alert_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ALERT_READ))
):
    """Get complete alert details and explainability evidence."""
    metrics.inc_requests()
    return service.get_alert_by_id(alert_id)


@router.post("/{alert_id}/ack", response_model=AlertAckResponse)
async def acknowledge_alert(
    http_request: Request,
    alert_id: str,
    request: AlertAckRequest = AlertAckRequest(),
    service: AlertService = Depends(get_alert_service),
    metrics: MetricsCollector = Depends(get_metrics),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ALERT_ACK)),
    _csrf = Depends(validate_csrf_token),
    audit = Depends(get_audit_logger)
):
    """Acknowledge an active alert by an authorized operator (OPERATOR, SUPERVISOR, ADMIN)."""
    metrics.inc_requests()
    snapshot = service.get_alert_snapshot(alert_id)
    ack_user = principal.username
    res = service.acknowledge_alert(alert_id=alert_id, acknowledged_by=ack_user)

    try:
        audit.log_event(
            action="ACK_ALERT",
            resource_type="alert",
            outcome="SUCCESS",
            principal=principal,
            resource_id=alert_id,
            request_id=http_request.headers.get("X-Request-ID"),
            details={"acknowledged_by": ack_user},
            fail_closed=True
        )
    except Exception:
        # Compensate: restore exact prior alert ACK state on audit failure
        try:
            service.restore_alert_snapshot(alert_id, snapshot)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Security audit trail recording failed; alert acknowledgement aborted."
        )
    return res



