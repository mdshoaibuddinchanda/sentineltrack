from typing import Optional
from fastapi import Header, Depends

try:
    from .services.camera_service import CameraService
    from .services.target_service import TargetService
    from .services.sighting_service import SightingService
    from .services.alert_service import AlertService
    from .services.route_service import RouteService
    from .services.analytics_service import AnalyticsWorker, get_analytics_worker
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
    an_m = importlib.import_module("08_backend.services.analytics_service")
    AnalyticsWorker, get_analytics_worker = an_m.AnalyticsWorker, an_m.get_analytics_worker
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


def get_target_service() -> TargetService:
    return TargetService()


def get_sighting_service() -> SightingService:
    return SightingService()


def get_alert_service() -> AlertService:
    return AlertService()


def get_route_service() -> RouteService:
    return RouteService()


def get_analytics_worker_dep() -> AnalyticsWorker:
    return get_analytics_worker()


# ============================================================
# PRIORITY 10 SECURITY / RBAC / AUDIT HOOKS (DEFERRED INTERFACES)
# ============================================================

def get_current_user_placeholder(
    x_operator_id: Optional[str] = Header(default="operator-default", alias="X-Operator-Id")
) -> str:
    """
    P10 Authentication Placeholder.
    Returns caller operator identity from header or default.
    Full JWT / RBAC authentication is deferred to Priority 10.
    """
    return x_operator_id or "operator-default"


def require_role(role: str):
    """P10 Role-Based Access Control decorator placeholder."""
    def role_checker(user: str = Depends(get_current_user_placeholder)):
        return user
    return role_checker


def record_audit_event(action: str, target: str, actor: str = "operator-default"):
    """P10 Audit Logging Hook. Records sensitive operations (target add, history search, alert ack)."""
    pass
