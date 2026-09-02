import importlib
from typing import Optional
from fastapi import Header, Depends


try:
    from .services.camera_service import CameraService
    from .services.target_service import TargetService
    from .services.sighting_service import SightingService
    from .services.alert_service import AlertService
    from .services.route_service import RouteService
    from .config import BackendConfig, get_backend_config
    from .metrics import MetricsCollector, get_metrics_collector
    from .event_bus import AsyncEventBus, get_event_bus
    from .websocket.manager import ConnectionManager, get_connection_manager
except (ImportError, ValueError):
    import importlib
    CameraService = importlib.import_module("08_backend.services.camera_service").CameraService
    TargetService = importlib.import_module("08_backend.services.target_service").TargetService
    SightingService = importlib.import_module("08_backend.services.sighting_service").SightingService
    AlertService = importlib.import_module("08_backend.services.alert_service").AlertService
    RouteService = importlib.import_module("08_backend.services.route_service").RouteService
    cfg_m = importlib.import_module("08_backend.config")
    BackendConfig, get_backend_config = cfg_m.BackendConfig, cfg_m.get_backend_config
    met_m = importlib.import_module("08_backend.metrics")
    MetricsCollector, get_metrics_collector = met_m.MetricsCollector, met_m.get_metrics_collector
    ev_m = importlib.import_module("08_backend.event_bus")
    AsyncEventBus, get_event_bus = ev_m.AsyncEventBus, ev_m.get_event_bus
    ws_m = importlib.import_module("08_backend.websocket.manager")
    ConnectionManager, get_connection_manager = ws_m.ConnectionManager, ws_m.get_connection_manager



def get_config() -> BackendConfig:
    return get_backend_config()


def get_metrics() -> MetricsCollector:
    return get_metrics_collector()


def get_bus() -> AsyncEventBus:
    return get_event_bus()


def get_ws_manager() -> ConnectionManager:
    return get_connection_manager()


def get_camera_service() -> CameraService:
    return CameraService()


def get_vms_service():
    service_m = importlib.import_module("08_backend.services.vms_service")
    return service_m.VMSIntegrationService()


def get_target_service() -> TargetService:
    return TargetService()


def get_sighting_service() -> SightingService:
    return SightingService()


def get_alert_service() -> AlertService:
    return AlertService()


def get_route_service() -> RouteService:
    return RouteService()


def get_analytics_worker_dep():
    try:
        from .services.analytics_service import get_analytics_worker
    except (ImportError, ValueError):
        get_analytics_worker = importlib.import_module("08_backend.services.analytics_service").get_analytics_worker
    return get_analytics_worker()



# ============================================================
# PRIORITY 10 SECURITY / RBAC / AUDIT HOOKS
# ============================================================

# 10_security always via importlib (module name starts with digit)
_sec_m = importlib.import_module("10_security")
UserRole = _sec_m.UserRole
Permission = _sec_m.Permission
AuthenticatedPrincipal = _sec_m.AuthenticatedPrincipal
get_security_config = _sec_m.get_security_config
get_security_repository = _sec_m.get_security_repository
get_session_manager = _sec_m.get_session_manager
get_audit_logger = _sec_m.get_audit_logger
_dep_m = importlib.import_module("10_security.dependencies")
get_current_principal = _dep_m.get_current_principal
get_optional_principal = _dep_m.get_optional_principal
require_permission = _dep_m.require_permission
require_role = _dep_m.require_role
validate_csrf_token = _dep_m.validate_csrf_token



def get_current_user_placeholder(
    principal: Optional[AuthenticatedPrincipal] = Depends(get_optional_principal),
    x_operator_id: Optional[str] = Header(default=None, alias="X-Operator-Id")
) -> str:
    """Backward-compatible user identity accessor."""
    if principal:
        return principal.username
    return x_operator_id or "operator-default"


def record_audit_event(
    action: str,
    target: str,
    actor: str = "system",
    outcome: str = "SUCCESS",
    details: Optional[dict] = None
):
    """P10 Structured Audit Logger bridge."""
    try:
        audit = get_audit_logger()
        audit.log_event(
            action=action,
            resource_type="operation",
            outcome=outcome,
            actor_username=actor,
            resource_id=target,
            details=details or {}
        )
    except Exception:
        pass

