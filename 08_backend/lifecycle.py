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

_STREAM_SUPERVISOR = None


def get_stream_supervisor():
    """Return the process-local stream supervisor, when live ingestion is enabled."""
    return _STREAM_SUPERVISOR


def _start_stream_ingestion(worker, scale_config):
    """Load persisted camera sources and connect them to the analytics queue."""
    if not scale_config.enable_stream_ingestion:
        logger.info("Live camera ingestion is disabled (SENTINEL_ENABLE_STREAM_INGESTION=false).")
        return None

    supervisor_m = importlib.import_module("11_scale_deployment.supervisor")
    database = importlib.import_module("00_foundation.registry.database")
    supervisor = supervisor_m.StreamSupervisor(
        config=scale_config,
        scheduler=worker.scheduler,
        on_frame_callback=worker.enqueue_frame,
    )

    cameras = database.get_all_cameras()
    registered = 0
    for camera in cameras:
        camera_id = str(camera.get("camera_id") or "").strip()
        primary_url = str(camera.get("rtsp_url") or "").strip()
        fallback_url = str(camera.get("hls_url") or "").strip()
        if not camera_id or (not primary_url and not fallback_url):
            continue
        # A camera marked non-live is retained in the registry but is not
        # repeatedly probed by the active process. It can be enabled later by
        # updating its registry record and restarting the worker.
        if camera.get("live") is False:
            continue
        if not primary_url:
            primary_url, fallback_url = fallback_url, None
        if supervisor.add_camera(camera_id, primary_url, fallback_url or None):
            registered += 1

    supervisor.start()
    logger.info("Live camera ingestion started with %s persisted camera sources.", registered)
    return supervisor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager handling startup and shutdown sequence according to process role."""
    config = get_backend_config()
    scale_config = get_scale_config()
    metrics = get_metrics_collector()
    logger.info(f"Starting {config.server.title} v{config.server.version} (role={scale_config.process_role})...")


    global _STREAM_SUPERVISOR
    worker = None
    event_bridge = None
    stream_supervisor = None

    # 1. Start Analytics Worker only if analytics is enabled for this process role ('all' or 'analytics')
    if scale_config.is_analytics_enabled():
        logger.info("Process role includes analytics: starting AnalyticsWorker...")
        analytics_m = importlib.import_module("08_backend.services.analytics_service")
        worker = analytics_m.get_analytics_worker()
        worker.start()
        try:
            stream_supervisor = _start_stream_ingestion(worker, scale_config)
            _STREAM_SUPERVISOR = stream_supervisor
        except Exception:
            logger.exception("Live camera ingestion could not be started; analytics API remains available.")
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
    if stream_supervisor:
        stream_supervisor.stop()
    _STREAM_SUPERVISOR = None
    if worker and worker.is_running():
        worker.stop()

    if event_bridge:
        event_bridge.stop_listener()

    logger.info(f"Shutdown complete. Total requests served: {metrics.total_requests}")
