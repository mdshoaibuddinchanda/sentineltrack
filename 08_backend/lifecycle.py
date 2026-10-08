import logging
import importlib
import os
import time
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


def _camera_stream_urls(
    camera: dict,
    scale_config,
    *,
    hls_authorized: bool = True,
) -> tuple[str, str]:
    """Resolve the process-local primary/fallback source without exposing credentials."""
    rtsp_url = str(camera.get("rtsp_url") or "").strip()
    hls_url = str(camera.get("hls_url") or "").strip()
    official_source = _is_official_source(camera)
    if (
        official_source
        and hls_authorized
        and scale_config.prefer_hls_for_official_feeds
        and hls_url
    ):
        return hls_url, rtsp_url
    if official_source:
        # Direct RTSP is independently reachable and remains usable during a
        # transient catalogue/CDN outage when an access grant is configured.
        # HLS is a fallback only when this process owns an authenticated
        # catalogue session whose cookie can be passed to FFmpeg.
        return rtsp_url, hls_url if (rtsp_url and hls_authorized) else ""
    return rtsp_url or hls_url, hls_url if rtsp_url else ""


def sync_camera_worker(camera_id: str) -> str:
    """Apply one committed registry change to the running local supervisor.

    This is deliberately process-local. In a sharded deployment the registry
    event bridge/control plane is responsible for notifying the owning shard.
    """
    supervisor = get_stream_supervisor()
    if supervisor is None:
        return "RESTART_REQUIRED"

    database = importlib.import_module("00_foundation.registry.database")
    camera = database.get_camera(camera_id)
    if not camera:
        supervisor.remove_camera(camera_id)
        return "REMOVED"

    supervisor.remove_camera(camera_id)
    if camera.get("live") is False:
        return "DISABLED"

    authorization_blocked = (
        not os.getenv("SENTINEL_ACCESS_PASSWORD", "").strip()
        or _STREAM_INGESTION_DIAGNOSTICS.get("code") in {"AUTH_REQUIRED", "AUTH_FAILED"}
    )
    if _is_official_source(camera) and authorization_blocked:
        return "SOURCE_BLOCKED"

    scale_config = get_scale_config()
    primary_url, fallback_url = _camera_stream_urls(
        camera,
        scale_config,
        hls_authorized=_CATALOGUE_CLIENT is not None,
    )
    if not primary_url:
        return "NOT_CONFIGURED"
    accepted = supervisor.add_camera(camera_id, primary_url, fallback_url or None)
    return "STARTED" if accepted else "SHARD_NOT_ASSIGNED"


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

    _CATALOGUE_CLIENT = None

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
        configured_attempts = int(os.getenv("SENTINEL_CATALOGUE_FETCH_ATTEMPTS", "3"))
    except ValueError:
        configured_attempts = 3
    max_attempts = min(5, max(1, configured_attempts))
    client = client_m.SentinelCatalogueClient()
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
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
                "catalogue_attempts": attempt,
                "blocked_camera_ids": [],
            })
            logger.info(
                "Organizer catalogue refreshed with %s cameras on attempt %s.",
                len(cameras),
                attempt,
            )
            return client, diagnostics
        except Exception as exc:
            last_exc = exc
            code = _catalogue_failure_code(exc)
            if code in {"AUTH_REQUIRED", "AUTH_FAILED"} or attempt >= max_attempts:
                break
            delay_s = min(4.0, float(2 ** (attempt - 1)))
            logger.warning(
                "Organizer catalogue attempt %s/%s failed (%s); retrying in %.1fs.",
                attempt,
                max_attempts,
                code,
                delay_s,
            )
            time.sleep(delay_s)

    assert last_exc is not None
    code = _catalogue_failure_code(last_exc)
    # Do not log a traceback for known authorization/configuration states.
    if code in {"AUTH_REQUIRED", "AUTH_FAILED"}:
        logger.warning("Official camera access unavailable: %s", last_exc)
    else:
        logger.warning(
            "Organizer catalogue refresh failed after %s attempt(s): %s",
            max_attempts,
            last_exc,
        )
    return None, {
        "enabled": True,
        "code": code,
        "message": str(last_exc),
        "catalogue_attempts": max_attempts,
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
    authorization_blocked = (
        not os.getenv("SENTINEL_ACCESS_PASSWORD", "").strip()
        or source_diagnostics.get("code") in {"AUTH_REQUIRED", "AUTH_FAILED"}
    )
    for camera in cameras:
        camera_id = str(camera.get("camera_id") or "").strip()
        official_source = _is_official_source(camera)
        if official_source and authorization_blocked:
            if camera_id:
                blocked_camera_ids.append(camera_id)
            continue

        primary_url, fallback_url = _camera_stream_urls(
            camera,
            scale_config,
            hls_authorized=catalogue_client is not None,
        )
        if not camera_id or (not primary_url and not fallback_url):
            if camera_id and official_source:
                blocked_camera_ids.append(camera_id)
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
    elif catalogue_client is None:
        previous_code = source_diagnostics.get("code", "CATALOGUE_ERROR")
        source_diagnostics["code"] = "CATALOGUE_STALE_RTSP_FALLBACK"
        source_diagnostics["message"] = (
            f"Catalogue refresh is unavailable ({previous_code}); {registered} previously "
            "authorized persisted direct RTSP source(s) are running without HLS fallback."
        )
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
