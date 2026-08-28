import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

try:
    from .config import get_backend_config
    from .metrics import get_metrics_collector
    from .services.analytics_service import get_analytics_worker
    from .websocket.manager import get_connection_manager
except (ImportError, ValueError):
    import importlib
    get_backend_config = importlib.import_module("08_backend.config").get_backend_config
    get_metrics_collector = importlib.import_module("08_backend.metrics").get_metrics_collector
    get_analytics_worker = importlib.import_module("08_backend.services.analytics_service").get_analytics_worker
    get_connection_manager = importlib.import_module("08_backend.websocket.manager").get_connection_manager

logger = logging.getLogger("sentineltrack.lifecycle")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager handling startup and shutdown sequence."""
    config = get_backend_config()
    metrics = get_metrics_collector()
    logger.info(f"Starting {config.server.title} v{config.server.version}...")

    # Start background analytics worker
    worker = get_analytics_worker()
    worker.start()

    yield

    # Shutdown sequence
    logger.info("Initiating graceful shutdown...")
    if worker.is_running():
        worker.stop()

    logger.info(f"Shutdown complete. Total requests served: {metrics.total_requests}")
