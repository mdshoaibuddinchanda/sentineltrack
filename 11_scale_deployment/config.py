import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScaleDeploymentConfig:
    """Configuration for scale, multi-camera scheduling, process roles, and deployment."""

    # Process Role: 'all' (API + WebSocket + Analytics in 1 process),
    #               'api' (HTTP + WebSocket only, no GPU models),
    #               'analytics' (Stream ingestion + GPU analytics worker only)
    process_role: str = field(
        default_factory=lambda: os.getenv("SENTINEL_PROCESS_ROLE", "all").strip().lower()
    )

    # Sharding & Multi-Worker Identity
    shard_count: int = field(
        default_factory=lambda: max(1, int(os.getenv("SENTINEL_SHARD_COUNT", "1")))
    )
    shard_index: int = field(
        default_factory=lambda: int(os.getenv("SENTINEL_SHARD_INDEX", "0"))
    )
    worker_id: str = field(
        default_factory=lambda: os.getenv("SENTINEL_WORKER_ID", "worker-0")
    )

    # Hardware & Model Enforcement
    require_gpu: bool = field(
        default_factory=lambda: os.getenv("SENTINEL_REQUIRE_GPU", "false").lower() in ("true", "1", "yes")
    )
    enable_cuda_fp16: bool = field(
        default_factory=lambda: os.getenv("SENTINEL_CUDA_FP16", "true").lower() in ("true", "1", "yes")
    )

    # Fair Scheduling & Adaptive Sampling
    base_sampling_fps: float = field(
        default_factory=lambda: float(os.getenv("SENTINEL_BASE_SAMPLING_FPS", "1.0"))
    )
    burst_sampling_fps: float = field(
        default_factory=lambda: float(os.getenv("SENTINEL_BURST_SAMPLING_FPS", "5.0"))
    )
    burst_duration_s: float = 5.0
    max_staleness_ms: float = field(
        default_factory=lambda: float(os.getenv("SENTINEL_MAX_STALENESS_MS", "1000.0"))
    )
    queue_max_size: int = field(
        default_factory=lambda: int(os.getenv("SENTINEL_QUEUE_MAX_SIZE", "10"))
    )

    # Micro-Batching
    micro_batch_size: int = field(
        default_factory=lambda: int(os.getenv("SENTINEL_BATCH_SIZE", "4"))
    )
    max_batch_wait_ms: float = field(
        default_factory=lambda: float(os.getenv("SENTINEL_MAX_BATCH_WAIT_MS", "10.0"))
    )

    # Database Connection Pool
    db_pool_min_size: int = field(
        default_factory=lambda: int(os.getenv("SENTINEL_DB_POOL_MIN", "2"))
    )
    db_pool_max_size: int = field(
        default_factory=lambda: int(os.getenv("SENTINEL_DB_POOL_MAX", "10"))
    )
    db_pool_timeout_s: float = field(
        default_factory=lambda: float(os.getenv("SENTINEL_DB_POOL_TIMEOUT", "10.0"))
    )

    # Event Bridge (PostgreSQL LISTEN/NOTIFY)
    enable_postgres_event_bridge: bool = field(
        default_factory=lambda: os.getenv("SENTINEL_PG_EVENT_BRIDGE", "false").lower() in ("true", "1", "yes")
    )

    # The full launcher explicitly enables ingestion. Keeping the library
    # default off makes API/test imports safe and prevents an accidental
    # direct import from opening camera connections.
    enable_stream_ingestion: bool = field(
        default_factory=lambda: os.getenv("SENTINEL_ENABLE_STREAM_INGESTION", "false").lower() in ("true", "1", "yes")
    )

    # Stream connection controls. These values are consumed by the OpenCV
    # reader; keeping them here makes the launcher configuration observable
    # and prevents failed RTSP sources from blocking a worker indefinitely.
    rtsp_connect_timeout_s: float = field(
        default_factory=lambda: max(1.0, float(os.getenv("RTSP_CONNECT_TIMEOUT", "10")))
    )
    stream_max_backoff_s: float = field(
        default_factory=lambda: max(1.0, float(os.getenv("STREAM_MAX_BACKOFF", "30")))
    )
    stream_failover_threshold: int = field(
        default_factory=lambda: max(1, int(os.getenv("STREAM_FAILOVER_THRESHOLD", "1")))
    )
    stream_stale_after_s: float = field(
        default_factory=lambda: max(5.0, float(os.getenv("STREAM_STALE_AFTER", "20")))
    )
    stream_recovery_interval_s: float = field(
        default_factory=lambda: max(30.0, float(os.getenv("STREAM_RECOVERY_INTERVAL", "300")))
    )
    prefer_hls_for_official_feeds: bool = field(
        default_factory=lambda: os.getenv("SENTINEL_PREFER_OFFICIAL_HLS", "true").lower() in ("true", "1", "yes")
    )
    refresh_catalogue_on_start: bool = field(
        default_factory=lambda: os.getenv("SENTINEL_REFRESH_CATALOGUE_ON_START", "true").lower() in ("true", "1", "yes")
    )

    def is_api_enabled(self) -> bool:
        return self.process_role in ("all", "api")

    def is_analytics_enabled(self) -> bool:
        return self.process_role in ("all", "analytics")


_GLOBAL_SCALE_CONFIG: Optional[ScaleDeploymentConfig] = None


def get_scale_config() -> ScaleDeploymentConfig:
    global _GLOBAL_SCALE_CONFIG
    if _GLOBAL_SCALE_CONFIG is None:
        _GLOBAL_SCALE_CONFIG = ScaleDeploymentConfig()
    return _GLOBAL_SCALE_CONFIG


def set_scale_config(config: Optional[ScaleDeploymentConfig]) -> None:
    global _GLOBAL_SCALE_CONFIG
    _GLOBAL_SCALE_CONFIG = config
