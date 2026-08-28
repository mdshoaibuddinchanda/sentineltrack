from typing import Any, Dict
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    git_sha: str = "f5f294f2fb6410f1bef0460228256923cc22b9e5"
    uptime_seconds: float


class ReadinessResponse(BaseModel):
    status: str  # "ready" | "degraded" | "unhealthy"
    components: Dict[str, bool]
    details: Dict[str, Any] = Field(default_factory=dict)


class MetricsResponse(BaseModel):
    metrics: Dict[str, Any]
