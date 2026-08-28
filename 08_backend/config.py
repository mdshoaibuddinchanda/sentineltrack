import os
import yaml
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    title: str = "SentinelTrack Intelligence API"
    version: str = "1.0.0"
    description: str = "Real-time Vehicle Trajectory, Target Matching & Alert Intelligence Engine"


class CORSConfig(BaseModel):
    allowed_origins: List[str] = Field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ])
    allow_credentials: bool = True
    allow_methods: List[str] = Field(default_factory=lambda: ["*"])
    allow_headers: List[str] = Field(default_factory=lambda: ["*"])


class DatabaseConfig(BaseModel):
    health_timeout_seconds: float = 3.0
    max_connections: int = 20


class PaginationConfig(BaseModel):
    default_limit: int = 50
    max_limit: int = 500


class WebSocketConfig(BaseModel):
    client_queue_size: int = 100
    heartbeat_interval_seconds: float = 15.0
    disconnect_timeout_seconds: float = 30.0


class AnalyticsWorkerConfig(BaseModel):
    micro_batch_size: int = 4
    max_batch_wait_ms: float = 10.0
    queue_max_size: int = 100
    enable_cuda_fp16: bool = True


class BackendConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    analytics_worker: AnalyticsWorkerConfig = Field(default_factory=AnalyticsWorkerConfig)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "BackendConfig":
        path = config_path or os.getenv("SENTINEL_BACKEND_CONFIG", "configs/backend.yaml")
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return cls(**data)
        return cls()


_GLOBAL_CONFIG: Optional[BackendConfig] = None


def get_backend_config() -> BackendConfig:
    global _GLOBAL_CONFIG
    if _GLOBAL_CONFIG is None:
        _GLOBAL_CONFIG = BackendConfig.load()
    return _GLOBAL_CONFIG
