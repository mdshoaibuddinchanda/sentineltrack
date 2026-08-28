try:
    from .health import router as health_router
    from .cameras import router as cameras_router
    from .targets import router as targets_router
    from .sightings import router as sightings_router
    from .alerts import router as alerts_router
    from .routes import router as routes_router
except (ImportError, ValueError):
    import importlib
    health_router = importlib.import_module("08_backend.routers.health").router
    cameras_router = importlib.import_module("08_backend.routers.cameras").router
    targets_router = importlib.import_module("08_backend.routers.targets").router
    sightings_router = importlib.import_module("08_backend.routers.sightings").router
    alerts_router = importlib.import_module("08_backend.routers.alerts").router
    routes_router = importlib.import_module("08_backend.routers.routes").router

__all__ = [
    "health_router",
    "cameras_router",
    "targets_router",
    "sightings_router",
    "alerts_router",
    "routes_router"
]
