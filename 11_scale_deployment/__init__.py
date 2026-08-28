"""
SentinelTrack Priority 11 - Scale, Deployment, Scheduling & Performance Module
"""
try:
    from .config import ScaleDeploymentConfig, get_scale_config, set_scale_config
    from .shard import get_camera_shard, is_camera_assigned_to_shard, filter_cameras_for_shard
    from .capacity import CapacityReport, compute_required_aggregate_fps, compute_max_cameras_for_node, evaluate_capacity
except (ImportError, ValueError):
    import importlib
    _cfg = importlib.import_module("11_scale_deployment.config")
    ScaleDeploymentConfig, get_scale_config, set_scale_config = _cfg.ScaleDeploymentConfig, _cfg.get_scale_config, _cfg.set_scale_config

    _shd = importlib.import_module("11_scale_deployment.shard")
    get_camera_shard, is_camera_assigned_to_shard, filter_cameras_for_shard = _shd.get_camera_shard, _shd.is_camera_assigned_to_shard, _shd.filter_cameras_for_shard

    _cap = importlib.import_module("11_scale_deployment.capacity")
    CapacityReport, compute_required_aggregate_fps, compute_max_cameras_for_node, evaluate_capacity = _cap.CapacityReport, _cap.compute_required_aggregate_fps, _cap.compute_max_cameras_for_node, _cap.evaluate_capacity

__all__ = [
    "ScaleDeploymentConfig",
    "get_scale_config",
    "set_scale_config",
    "get_camera_shard",
    "is_camera_assigned_to_shard",
    "filter_cameras_for_shard",
    "FairStreamScheduler",
    "StreamSupervisor",
    "CameraStreamWorker",
    "CapacityReport",
    "compute_required_aggregate_fps",
    "compute_max_cameras_for_node",
    "evaluate_capacity",
    "PipelineProfiler",
    "ResourceMonitor",
    "PostgresEventBridge",
    "get_event_bridge",
    "check_scale_health"
]


def __getattr__(name: str):
    import importlib
    if name == "FairStreamScheduler":
        _sch = importlib.import_module("11_scale_deployment.scheduler")
        return _sch.FairStreamScheduler
    elif name in ("StreamSupervisor", "CameraStreamWorker"):
        _sup = importlib.import_module("11_scale_deployment.supervisor")
        return getattr(_sup, name)
    elif name == "PipelineProfiler":
        _prf = importlib.import_module("11_scale_deployment.profiling")
        return _prf.PipelineProfiler
    elif name == "ResourceMonitor":
        _res = importlib.import_module("11_scale_deployment.resource_monitor")
        return _res.ResourceMonitor
    elif name in ("PostgresEventBridge", "get_event_bridge"):
        _evb = importlib.import_module("11_scale_deployment.event_bridge")
        return getattr(_evb, name)
    elif name == "check_scale_health":
        _hlth = importlib.import_module("11_scale_deployment.health")
        return _hlth.check_scale_health
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

