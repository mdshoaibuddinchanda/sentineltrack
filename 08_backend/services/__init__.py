try:
    from .camera_service import CameraService
    from .target_service import TargetService
    from .sighting_service import SightingService
    from .alert_service import AlertService
    from .route_service import RouteService
except (ImportError, ValueError):
    import importlib
    CameraService = importlib.import_module("08_backend.services.camera_service").CameraService
    TargetService = importlib.import_module("08_backend.services.target_service").TargetService
    SightingService = importlib.import_module("08_backend.services.sighting_service").SightingService
    AlertService = importlib.import_module("08_backend.services.alert_service").AlertService
    RouteService = importlib.import_module("08_backend.services.route_service").RouteService

__all__ = [
    "CameraService",
    "TargetService",
    "SightingService",
    "AlertService",
    "RouteService",
    "AnalyticsWorker",
    "get_analytics_worker"
]


def __getattr__(name: str):
    import importlib
    if name in ("AnalyticsWorker", "get_analytics_worker"):
        an_m = importlib.import_module("08_backend.services.analytics_service")
        return getattr(an_m, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

