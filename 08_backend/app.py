import time
import uuid
import logging
import importlib
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# --- Relative imports for 08_backend package ---
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
    from .routers.auth import router as auth_router
    from .routers.users import router as users_router
    from .routers.audit import router as audit_router
except (ImportError, ValueError):
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
    auth_router = importlib.import_module("08_backend.routers.auth").router
    users_router = importlib.import_module("08_backend.routers.users").router
    audit_router = importlib.import_module("08_backend.routers.audit").router

# --- 10_security imports (always via importlib — module name starts with digit) ---
_sec_m = importlib.import_module("10_security")
get_security_config = _sec_m.get_security_config
_mid_m = importlib.import_module("10_security.middleware")
SecurityHeadersMiddleware = _mid_m.SecurityHeadersMiddleware

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
    sec_config = get_security_config()

    is_prod = sec_config.env == "production"
    docs_url = None if is_prod else "/docs"
    redoc_url = None if is_prod else "/redoc"
    openapi_url = None if is_prod else "/openapi.json"

    app = FastAPI(
        title=config.server.title,
        version=config.server.version,
        description=config.server.description,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url
    )


    # 1. Security Headers Middleware (outermost so all responses get headers)
    app.add_middleware(SecurityHeadersMiddleware)

    # 2. CORS Middleware — use allowed_origins from security config (restrictive in prod)
    allowed_origins = sec_config.allowed_origins or config.cors.allowed_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "Authorization"]
    )

    # 3. Correlation ID & Latency Middleware
    app.add_middleware(RequestCorrelationMiddleware)

    # 4. Exception Handlers
    app.add_exception_handler(SentinelTrackAPIError, sentineltrack_exception_handler)
    app.add_exception_handler(Exception, global_unhandled_exception_handler)

    # 5. Include Routers — auth/users/audit first so they appear first in docs
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(audit_router)
    app.include_router(health_router)
    app.include_router(cameras_router)
    app.include_router(targets_router)
    app.include_router(sightings_router)
    app.include_router(alerts_router)
    app.include_router(routes_router)
    app.include_router(websocket_router)

    return app


app = create_app()

