import logging
import importlib
from contextlib import asynccontextmanager
from fastapi import FastAPI

try:
    from .config import get_backend_config
    from .metrics import get_metrics_collector
    from .websocket.manager import get_connection_manager
except (ImportError, ValueError):
    get_backend_config = importlib.import_module("08_backend.config").get_backend_config
    get_metrics_collector = importlib.import_module("08_backend.metrics").get_metrics_collector
    get_connection_manager = importlib.import_module("08_backend.websocket.manager").get_connection_manager

get_scale_config = importlib.import_module("11_scale_deployment.config").get_scale_config


logger = logging.getLogger("sentineltrack.lifecycle")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager handling startup and shutdown sequence according to process role."""
    config = get_backend_config()
    scale_config = get_scale_config()
    metrics = get_metrics_collector()
    logger.info(f"Starting {config.server.title} v{config.server.version} (role={scale_config.process_role})...")


    worker = None
    event_bridge = None

    # 1. Start Analytics Worker only if analytics is enabled for this process role ('all' or 'analytics')
    if scale_config.is_analytics_enabled():
        logger.info("Process role includes analytics: starting AnalyticsWorker...")
        analytics_m = importlib.import_module("08_backend.services.analytics_service")
        worker = analytics_m.get_analytics_worker()
        worker.start()
    else:
        logger.info("Process role is API-only (role=api): GPU AnalyticsWorker initialization skipped.")


    # 2. Start PostgreSQL Event Bridge listener if configured and API is enabled
    if scale_config.enable_postgres_event_bridge and scale_config.is_api_enabled():
        logger.info("Starting PostgresEventBridge listener for split-process notifications...")
        bridge_m = importlib.import_module("11_scale_deployment.event_bridge")
        event_bridge = bridge_m.get_event_bridge()
        event_bridge.start_listener()


    yield

    # 3. Shutdown sequence
    logger.info("Initiating graceful shutdown...")
    if worker and worker.is_running():
        worker.stop()

    if event_bridge:
        event_bridge.stop_listener()

    logger.info(f"Shutdown complete. Total requests served: {metrics.total_requests}")

