from typing import List, Optional
import importlib
from fastapi import APIRouter, Depends, Query

try:
    from ..schemas.alerts import AlertResponse, AlertListResponse, AlertAckRequest, AlertAckResponse
    from ..services.alert_service import AlertService
    from ..dependencies import get_alert_service, get_metrics, record_audit_event, get_current_user_placeholder
    from ..metrics import MetricsCollector
except (ImportError, ValueError):
    alt_m = importlib.import_module("08_backend.schemas.alerts")
    AlertResponse, AlertListResponse, AlertAckRequest, AlertAckResponse = alt_m.AlertResponse, alt_m.AlertListResponse, alt_m.AlertAckRequest, alt_m.AlertAckResponse
    AlertService = importlib.import_module("08_backend.services.alert_service").AlertService
    dep_m = importlib.import_module("08_backend.dependencies")
    get_alert_service, get_metrics, record_audit_event, get_current_user_placeholder = dep_m.get_alert_service, dep_m.get_metrics, dep_m.record_audit_event, dep_m.get_current_user_placeholder
    MetricsCollector = importlib.import_module("08_backend.metrics").MetricsCollector

router = APIRouter(prefix="/api/v1/alerts", tags=["Target Alerts & Incident Response"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    unacknowledged: bool = Query(default=False, description="Filter for unacknowledged alerts only"),
    camera_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: AlertService = Depends(get_alert_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """List real-time target match alerts with acknowledgement and camera filters."""
    metrics.inc_requests()
    alerts = service.query_alerts(
        unacknowledged_only=unacknowledged,
        camera_id=camera_id,
        limit=limit,
        offset=offset
    )
    unack_count = sum(1 for a in alerts if not a.acknowledged)
    return AlertListResponse(items=alerts, total=len(alerts), unacknowledged_count=unack_count)


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert_detail(
    alert_id: str,
    service: AlertService = Depends(get_alert_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Get complete alert details and explainability evidence."""
    metrics.inc_requests()
    return service.get_alert_by_id(alert_id)


@router.post("/{alert_id}/ack", response_model=AlertAckResponse)
async def acknowledge_alert(
    alert_id: str,
    request: AlertAckRequest = AlertAckRequest(),
    service: AlertService = Depends(get_alert_service),
    metrics: MetricsCollector = Depends(get_metrics),
    current_user: str = Depends(get_current_user_placeholder)
):
    """Acknowledge an active alert by an authorized operator."""
    metrics.inc_requests()
    ack_user = request.acknowledged_by or current_user
    res = service.acknowledge_alert(alert_id=alert_id, acknowledged_by=ack_user)
    record_audit_event(action="ACK_ALERT", target=alert_id, actor=ack_user)
    return res
