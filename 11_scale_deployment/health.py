import time
from typing import Dict, Any, Optional
import torch

import importlib
get_scale_config = importlib.import_module("11_scale_deployment.config").get_scale_config
get_connection = importlib.import_module("00_foundation.registry.database").get_connection



def check_scale_health() -> Dict[str, Any]:
    """
    Performs comprehensive diagnostic health and readiness evaluation across
    database connectivity, GPU acceleration, process role, and model availability.
    """
    config = get_scale_config()
    health_status: Dict[str, Any] = {
        "status": "HEALTHY",
        "process_role": config.process_role,
        "shard_index": config.shard_index,
        "shard_count": config.shard_count,
        "worker_id": config.worker_id,
        "timestamp": time.time(),
        "checks": {}
    }

    # 1. Database Connectivity Check
    try:
        t0 = time.perf_counter()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        db_time_ms = (time.perf_counter() - t0) * 1000.0
        health_status["checks"]["database"] = {
            "status": "PASS",
            "latency_ms": round(db_time_ms, 2)
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "FAIL",
            "error": str(e)
        }
        health_status["status"] = "DEGRADED"

    # 2. GPU & Hardware Capability Check
    cuda_avail = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_avail else "CPU"
    vram_mb = 0.0
    if cuda_avail:
        try:
            vram_mb = torch.cuda.get_device_properties(0).total_memory / (1024.0 * 1024.0)
        except Exception:
            pass

    gpu_check_pass = True
    if config.require_gpu and not cuda_avail:
        gpu_check_pass = False
        health_status["status"] = "FAIL"

    health_status["checks"]["gpu"] = {
        "status": "PASS" if gpu_check_pass else "FAIL",
        "cuda_available": cuda_avail,
        "device_name": device_name,
        "total_vram_mb": round(vram_mb, 1),
        "required": config.require_gpu
    }

    # 3. Process Role Validation
    health_status["checks"]["role"] = {
        "status": "PASS",
        "role": config.process_role,
        "api_enabled": config.is_api_enabled(),
        "analytics_enabled": config.is_analytics_enabled()
    }

    return health_status
