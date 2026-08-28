import time
import uuid
import logging
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from .config import get_backend_config
    from .lifecycle import lifespan
    from .errors import (
        SentinelTrackAPIError,
        sentineltrack_exception_handler,
        global_unhandled_exception_handler
    )
    from .routers import (
        health_router,
        cameras_router,
        targets_router,
        sightings_router,
        alerts_router,
        routes_router
    )
    from .websocket.routes import router as websocket_router
except (ImportError, ValueError):
    import importlib
    get_backend_config = importlib.import_module("08_backend.config").get_backend_config
    lifespan = importlib.import_module("08_backend.lifecycle").lifespan
    err_m = importlib.import_module("08_backend.errors")
    SentinelTrackAPIError = err_m.SentinelTrackAPIError
    sentineltrack_exception_handler = err_m.sentineltrack_exception_handler
    global_unhandled_exception_handler = err_m.global_unhandled_exception_handler
    rts_m = importlib.import_module("08_backend.routers")
    health_router = rts_m.health_router
    cameras_router = rts_m.cameras_router
    targets_router = rts_m.targets_router
    sightings_router = rts_m.sightings_router
    alerts_router = rts_m.alerts_router
    routes_router = rts_m.routes_router
    websocket_router = importlib.import_module("08_backend.websocket.routes").router

logger = logging.getLogger("sentineltrack.api")


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware adding X-Request-ID and measuring execution latency."""

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start_time = time.perf_counter()
        
        response: Response = await call_next(request)
        
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-Ms"] = f"{latency_ms:.2f}"
        return response


def create_app() -> FastAPI:
    config = get_backend_config()

    app = FastAPI(
        title=config.server.title,
        version=config.server.version,
        description=config.server.description,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors.allowed_origins,
        allow_credentials=config.cors.allow_credentials,
        allow_methods=config.cors.allow_methods,
        allow_headers=config.cors.allow_headers
    )

    # 2. Correlation ID & Latency Middleware
    app.add_middleware(RequestCorrelationMiddleware)

    # 3. Exception Handlers
    app.add_exception_handler(SentinelTrackAPIError, sentineltrack_exception_handler)
    app.add_exception_handler(Exception, global_unhandled_exception_handler)

    # 4. Include Routers
    app.include_router(health_router)
    app.include_router(cameras_router)
    app.include_router(targets_router)
    app.include_router(sightings_router)
    app.include_router(alerts_router)
    app.include_router(routes_router)
    app.include_router(websocket_router)

    return app


app = create_app()
