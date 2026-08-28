"""
SentinelTrack Priority 11 - Scale, Deployment, Scheduling & Performance Module
"""
try:
    from .config import ScaleDeploymentConfig, get_scale_config, set_scale_config
    from .shard import get_camera_shard, is_camera_assigned_to_shard, filter_cameras_for_shard
    from .scheduler import FairStreamScheduler
    from .supervisor import StreamSupervisor, CameraStreamWorker
    from .capacity import CapacityReport, compute_required_aggregate_fps, compute_max_cameras_for_node, evaluate_capacity
    from .profiling import PipelineProfiler
    from .resource_monitor import ResourceMonitor
    from .event_bridge import PostgresEventBridge, get_event_bridge
    from .health import check_scale_health
except (ImportError, ValueError):
    import importlib
    _cfg = importlib.import_module("11_scale_deployment.config")
    ScaleDeploymentConfig, get_scale_config, set_scale_config = _cfg.ScaleDeploymentConfig, _cfg.get_scale_config, _cfg.set_scale_config

    _shd = importlib.import_module("11_scale_deployment.shard")
    get_camera_shard, is_camera_assigned_to_shard, filter_cameras_for_shard = _shd.get_camera_shard, _shd.is_camera_assigned_to_shard, _shd.filter_cameras_for_shard

    _sch = importlib.import_module("11_scale_deployment.scheduler")
    FairStreamScheduler = _sch.FairStreamScheduler

    _sup = importlib.import_module("11_scale_deployment.supervisor")
    StreamSupervisor, CameraStreamWorker = _sup.StreamSupervisor, _sup.CameraStreamWorker

    _cap = importlib.import_module("11_scale_deployment.capacity")
    CapacityReport, compute_required_aggregate_fps, compute_max_cameras_for_node, evaluate_capacity = _cap.CapacityReport, _cap.compute_required_aggregate_fps, _cap.compute_max_cameras_for_node, _cap.evaluate_capacity

    _prf = importlib.import_module("11_scale_deployment.profiling")
    PipelineProfiler = _prf.PipelineProfiler

    _res = importlib.import_module("11_scale_deployment.resource_monitor")
    ResourceMonitor = _res.ResourceMonitor

    _evb = importlib.import_module("11_scale_deployment.event_bridge")
    PostgresEventBridge, get_event_bridge = _evb.PostgresEventBridge, _evb.get_event_bridge

    _hlth = importlib.import_module("11_scale_deployment.health")
    check_scale_health = _hlth.check_scale_health

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
