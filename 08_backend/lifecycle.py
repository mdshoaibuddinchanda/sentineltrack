import logging
import importlib
from copy import deepcopy
from contextlib import asynccontextmanager
from urllib.parse import urlparse
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
_CATALOGUE_CLIENT = None
_STREAM_INGESTION_DIAGNOSTICS = {
    "enabled": False,
    "code": "DISABLED",
    "message": "Live camera ingestion is disabled.",
    "blocked_camera_ids": [],
}


def get_stream_supervisor():
    """Return the process-local stream supervisor, when live ingestion is enabled."""
    return _STREAM_SUPERVISOR


def get_stream_ingestion_diagnostics():
    """Return a secret-free snapshot of catalogue and source readiness."""
    return deepcopy(_STREAM_INGESTION_DIAGNOSTICS)


def _is_official_source(camera: dict) -> bool:
    for key in ("rtsp_url", "hls_url", "webrtc_url"):
        value = str(camera.get(key) or "").strip()
        if not value:
            continue
        host = (urlparse(value).hostname or "").lower()
        if host.endswith("sentinelgujarat.in") or host.endswith("corp8.cloud"):
            return True
    return False


def _catalogue_failure_code(exc: Exception) -> str:
    code = str(getattr(exc, "code", "CATALOGUE_ERROR"))
    message = str(exc).lower()
    dns_markers = (
        "getaddrinfo failed",
        "name resolution",
        "failed to resolve",
        "nodename nor servname",
    )
    return "DNS_FAILURE" if any(marker in message for marker in dns_markers) else code


def _refresh_catalogue(database, scale_config):
    """Refresh persisted camera metadata and retain the organizer session."""
    global _CATALOGUE_CLIENT

    if not scale_config.refresh_catalogue_on_start:
        return None, {
            "enabled": True,
            "code": "CATALOGUE_REFRESH_DISABLED",
            "message": "Startup catalogue refresh is disabled; persisted sources will be used.",
            "blocked_camera_ids": [],
        }

    client_m = importlib.import_module("00_foundation.catalogue.client")
    parser_m = importlib.import_module("00_foundation.catalogue.parser")
    try:
        client = client_m.SentinelCatalogueClient()
        payload = client.fetch()
        cameras = parser_m.parse_catalogue(payload, base_host=client.effective_host)
        for camera in cameras:
            database.upsert_camera(camera)
        _CATALOGUE_CLIENT = client
        diagnostics = client.diagnostics()
        diagnostics.update({
            "enabled": True,
            "code": "READY",
            "message": f"Organizer catalogue refreshed with {len(cameras)} cameras.",
            "catalogue_camera_count": len(cameras),
            "blocked_camera_ids": [],
        })
        logger.info("Organizer catalogue refreshed with %s cameras.", len(cameras))
        return client, diagnostics
    except Exception as exc:
        code = _catalogue_failure_code(exc)
        # Do not log a traceback for a known missing/rejected password. It is
        # an actionable provisioning state, not an application crash.
        if code in {"AUTH_REQUIRED", "AUTH_FAILED"}:
            logger.warning("Official camera access unavailable: %s", exc)
        else:
            logger.warning("Organizer catalogue refresh failed: %s", exc)
        return None, {
            "enabled": True,
            "code": code,
            "message": str(exc),
            "blocked_camera_ids": [],
        }


def _start_stream_ingestion(worker, scale_config):
    """Load persisted camera sources and connect them to the analytics queue."""
    global _STREAM_INGESTION_DIAGNOSTICS
    if not scale_config.enable_stream_ingestion:
        logger.info("Live camera ingestion is disabled (SENTINEL_ENABLE_STREAM_INGESTION=false).")
        _STREAM_INGESTION_DIAGNOSTICS = {
            "enabled": False,
            "code": "DISABLED",
            "message": "Live camera ingestion is disabled.",
            "blocked_camera_ids": [],
        }
        return None

    supervisor_m = importlib.import_module("11_scale_deployment.supervisor")
    database = importlib.import_module("00_foundation.registry.database")
    catalogue_client, source_diagnostics = _refresh_catalogue(database, scale_config)
    supervisor = supervisor_m.StreamSupervisor(
        config=scale_config,
        scheduler=worker.scheduler,
        on_frame_callback=worker.enqueue_frame,
        http_cookie_provider=(catalogue_client.get_ffmpeg_cookies if catalogue_client else None),
        source_diagnostics=source_diagnostics,
    )

    cameras = database.get_all_cameras()
    registered = 0
    blocked_camera_ids: list[str] = []
    blocking_codes = {
        "AUTH_REQUIRED",
        "AUTH_FAILED",
        "DNS_FAILURE",
        "CATALOGUE_UNREACHABLE",
        "CATALOGUE_INVALID_RESPONSE",
        "CATALOGUE_ERROR",
    }
    for camera in cameras:
        camera_id = str(camera.get("camera_id") or "").strip()
        rtsp_url = str(camera.get("rtsp_url") or "").strip()
        hls_url = str(camera.get("hls_url") or "").strip()
        official_source = _is_official_source(camera)
        if official_source and source_diagnostics.get("code") in blocking_codes:
            if camera_id:
                blocked_camera_ids.append(camera_id)
            continue

        if official_source and scale_config.prefer_hls_for_official_feeds and hls_url:
            primary_url, fallback_url = hls_url, rtsp_url
        elif official_source:
            # In the RTSP-first inference profile, do not park a worker on
            # the organizer's encrypted portal HLS playlist after a transient
            # RTSP failure. That playlist is the browser/remote delivery path
            # and is not decodable by every local OpenCV FFmpeg build. Retry
            # the direct TCP source instead; HLS can still be selected via
            # SENTINEL_PREFER_OFFICIAL_HLS=true.
            primary_url, fallback_url = rtsp_url, None
        else:
            primary_url, fallback_url = rtsp_url, hls_url
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
    source_diagnostics.update({
        "configured_camera_count": len(cameras),
        "registered_camera_count": registered,
        "blocked_camera_count": len(blocked_camera_ids),
        "blocked_camera_ids": blocked_camera_ids,
    })
    if blocked_camera_ids:
        source_diagnostics["message"] = (
            f"{len(blocked_camera_ids)} official cameras are blocked: "
            f"{source_diagnostics.get('message', 'source access unavailable')}"
        )
    elif registered == 0:
        source_diagnostics["code"] = "NO_CONFIGURED_SOURCES"
        source_diagnostics["message"] = "No enabled camera source is available to the worker."
    _STREAM_INGESTION_DIAGNOSTICS = source_diagnostics
    logger.info("Live camera ingestion started with %s persisted camera sources.", registered)
    return supervisor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager handling startup and shutdown sequence according to process role."""
    config = get_backend_config()
    scale_config = get_scale_config()
    metrics = get_metrics_collector()
    logger.info(f"Starting {config.server.title} v{config.server.version} (role={scale_config.process_role})...")


    global _STREAM_SUPERVISOR, _STREAM_INGESTION_DIAGNOSTICS
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
        except Exception as exc:
            _STREAM_INGESTION_DIAGNOSTICS = {
                "enabled": True,
                "code": "STARTUP_ERROR",
                "message": f"Live camera ingestion could not start: {exc}",
                "blocked_camera_ids": [],
            }
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
    _STREAM_INGESTION_DIAGNOSTICS = {
        "enabled": False,
        "code": "STOPPED",
        "message": "Live camera ingestion has stopped.",
        "blocked_camera_ids": [],
    }
    if worker and worker.is_running():
        worker.stop()

    if event_bridge:
        event_bridge.stop_listener()

    logger.info(f"Shutdown complete. Total requests served: {metrics.total_requests}")
