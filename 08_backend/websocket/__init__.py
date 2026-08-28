try:
    from .manager import ConnectionManager, get_connection_manager
    from .routes import router as websocket_router
except (ImportError, ValueError):
    import importlib
    mgr_m = importlib.import_module("08_backend.websocket.manager")
    ConnectionManager, get_connection_manager = mgr_m.ConnectionManager, mgr_m.get_connection_manager
    websocket_router = importlib.import_module("08_backend.websocket.routes").router

__all__ = ["ConnectionManager", "get_connection_manager", "websocket_router"]
