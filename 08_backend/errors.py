from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse


class SentinelTrackAPIError(Exception):
    """Base API exception with standard error code, message, and status code."""
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_SERVER_ERROR"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TargetNotFoundError(SentinelTrackAPIError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "TARGET_NOT_FOUND"


class CameraNotFoundError(SentinelTrackAPIError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "CAMERA_NOT_FOUND"


class AlertNotFoundError(SentinelTrackAPIError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "ALERT_NOT_FOUND"


class DuplicateTargetError(SentinelTrackAPIError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "DUPLICATE_TARGET"


class DatabaseUnavailableError(SentinelTrackAPIError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "DATABASE_UNAVAILABLE"


class RoutePersistenceAPIError(SentinelTrackAPIError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "ROUTE_PERSISTENCE_ERROR"


class InvalidQueryParameterError(SentinelTrackAPIError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "INVALID_QUERY_PARAMETER"


async def sentineltrack_exception_handler(request: Request, exc: SentinelTrackAPIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )


async def global_unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred.",
                "details": {}
            }
        }
    )
