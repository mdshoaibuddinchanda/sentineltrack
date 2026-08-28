try:
    from .app import app, create_app
    from .config import BackendConfig, get_backend_config
    from .metrics import MetricsCollector, get_metrics_collector
    from .event_bus import AsyncEventBus, get_event_bus
except (ImportError, ValueError):
    import importlib
    app_m = importlib.import_module("08_backend.app")
    app, create_app = app_m.app, app_m.create_app
    cfg_m = importlib.import_module("08_backend.config")
    BackendConfig, get_backend_config = cfg_m.BackendConfig, cfg_m.get_backend_config
    met_m = importlib.import_module("08_backend.metrics")
    MetricsCollector, get_metrics_collector = met_m.MetricsCollector, met_m.get_metrics_collector
    ev_m = importlib.import_module("08_backend.event_bus")
    AsyncEventBus, get_event_bus = ev_m.AsyncEventBus, ev_m.get_event_bus

__all__ = [
    "app",
    "create_app",
    "BackendConfig",
    "get_backend_config",
    "MetricsCollector",
    "get_metrics_collector",
    "AsyncEventBus",
    "get_event_bus"
]
