from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from .config import SecurityConfig, get_security_config


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects OWASP and NIST recommended HTTP security response headers
    and enforces appropriate caching policies on sensitive API endpoints.
    """

    def __init__(self, app, config: SecurityConfig | None = None):
        super().__init__(app)
        self.config = config or get_security_config()

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 1. Standard Hardening Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"

        # 2. Content Security Policy (allows local assets, websockets, and OSM basemap tiles)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://*.tile.openstreetmap.org; "
            "connect-src 'self' ws: wss: http: https:; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "base-uri 'self';"
        )

        # 3. Cache-Control for Authentication and Sensitive Resources
        path = request.url.path
        if any(prefix in path for prefix in ("/api/v1/auth", "/api/v1/users", "/api/v1/audit", "/api/v1/targets", "/api/v1/alerts")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"

        # 4. HSTS strictly in Production HTTPS mode (do not poison local development)
        if self.config.env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        return response

