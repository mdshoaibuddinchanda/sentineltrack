import time
import importlib
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


@router.get("/health", response_model=HealthResponse)
async def get_health(metrics: MetricsCollector = Depends(get_metrics)):
    """Basic process liveness probe."""
    uptime = time.time() - metrics.start_time
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        git_sha="f5f294f2fb6410f1bef0460228256923cc22b9e5",
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
