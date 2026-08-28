import time
import importlib
from typing import Optional
from fastapi import APIRouter, Depends, Response, status

try:
    from ..schemas.health import HealthResponse, ReadinessResponse, MetricsResponse
    from ..metrics import MetricsCollector
    from ..dependencies import get_metrics
except (ImportError, ValueError):
    hlth_m = importlib.import_module("08_backend.schemas.health")
    HealthResponse, ReadinessResponse, MetricsResponse = hlth_m.HealthResponse, hlth_m.ReadinessResponse, hlth_m.MetricsResponse
    MetricsCollector = importlib.import_module("08_backend.metrics").MetricsCollector
    get_metrics = importlib.import_module("08_backend.dependencies").get_metrics

router = APIRouter(tags=["Health & Diagnostics"])


import os
import subprocess

_CACHED_GIT_SHA: Optional[str] = None

def get_current_git_sha() -> str:
    global _CACHED_GIT_SHA
    if _CACHED_GIT_SHA is not None:
        return _CACHED_GIT_SHA

    env_sha = os.getenv("SENTINEL_GIT_SHA") or os.getenv("GIT_SHA")
    if env_sha:
        _CACHED_GIT_SHA = env_sha
        return _CACHED_GIT_SHA

    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2.0
        )
        if res.returncode == 0 and res.stdout.strip():
            _CACHED_GIT_SHA = res.stdout.strip()
            return _CACHED_GIT_SHA
    except Exception:
        pass

    _CACHED_GIT_SHA = "unknown"
    return _CACHED_GIT_SHA


@router.get("/health", response_model=HealthResponse)
async def get_health(metrics: MetricsCollector = Depends(get_metrics)):
    """Basic process liveness probe."""
    metrics.inc_requests()
    uptime = time.time() - metrics.start_time
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        git_sha=get_current_git_sha(),
        uptime_seconds=round(uptime, 2)
    )



@router.get("/ready", response_model=ReadinessResponse)
async def get_readiness(response: Response):
    """Deep readiness probe checking PostgreSQL/PostGIS, camera registry, and route engine dependencies."""
    components = {
        "database": False,
        "postgis": False,
        "camera_registry": False,
        "target_repository": False,
        "route_engine": True
    }
    details = {}

    try:
        db = importlib.import_module("00_foundation.registry.database")
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            r = cur.fetchone()
            if r and r[0] == 1:
                components["database"] = True

            # Check PostGIS extension
            cur.execute("SELECT PostGIS_Version();")
            pgis_v = cur.fetchone()
            if pgis_v:
                components["postgis"] = True
                details["postgis_version"] = pgis_v[0]

            # Check camera registry table
            cur.execute("SELECT COUNT(*) FROM cameras;")
            cam_cnt = cur.fetchone()
            if cam_cnt is not None:
                components["camera_registry"] = True
                details["camera_count"] = cam_cnt[0]

            # Check vehicle sightings table
            cur.execute("SELECT COUNT(*) FROM vehicle_sightings;")
            s_cnt = cur.fetchone()
            if s_cnt is not None:
                components["target_repository"] = True
                details["sighting_count"] = s_cnt[0]

        conn.close()
    except Exception as e:
        details["error"] = str(e)

    # 2. Check Analytics Worker & Computer Vision Models
    try:
        worker_mod = importlib.import_module("08_backend.services.analytics_service")
        worker = worker_mod.get_analytics_worker()
        worker._lazy_init_models()
        worker_status = worker.get_status()
        models_loaded = worker_status.get("models_loaded", {})

        components["analytics_worker"] = worker is not None
        components["vehicle_detector"] = models_loaded.get("detector", False)
        components["tracker"] = models_loaded.get("tracker", False)
        components["plate_detector"] = models_loaded.get("plate_detector", False)
        components["ocr_pipeline"] = models_loaded.get("ocr_pipeline", False)
        components["target_pipeline"] = models_loaded.get("target_pipeline", False)
        details["models"] = models_loaded
        details["worker_running"] = worker.is_running()
    except Exception as e:
        components["analytics_worker"] = False
        details["analytics_error"] = str(e)

    # 3. Check P7 Route Engine Pipeline
    try:
        p7_mod = importlib.import_module("07_route_engine.pipeline")
        p7_pipe = p7_mod.RouteEnginePipeline()
        components["route_engine"] = bool(p7_pipe.camera_repo is not None and p7_pipe.sighting_repo is not None)
    except Exception as e:
        components["route_engine"] = False
        details["route_engine_error"] = str(e)

    all_ready = all(components.values())
    if all_ready:
        return ReadinessResponse(status="ready", components=components, details=details)
    else:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ReadinessResponse(status="degraded", components=components, details=details).model_dump()
        )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics_snapshot(metrics: MetricsCollector = Depends(get_metrics)):
    """Returns operational JSON metrics snapshot."""
    return MetricsResponse(metrics=metrics.snapshot())
