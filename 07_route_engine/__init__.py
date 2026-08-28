try:
    from .models import (
        LocationQuality, TimeSource, TimeQuality, FeasibilityClass, TrajectoryStatus,
        CameraGeo, EventTimeInfo, RouteSighting, RouteSegment, TargetTrajectory, TrajectorySummary
    )
    from .config import RouteEngineConfig
    from .spatial import haversine_distance_m, validate_coordinates, calculate_segment_distance
    from .time_mapping import resolve_event_time_info, compute_segment_time_delta
    from .feasibility import evaluate_segment_feasibility
    from .trajectory import solve_best_trajectory_dag, collapse_same_camera_dwell_sightings
    from .confidence import evaluate_trajectory_confidence_and_reasons
    from .geojson import export_trajectory_to_geojson
    from .camera_repository import BaseCameraRepository, PostgresCameraRepository, InMemoryCameraRepository
    from .sighting_repository import SightingRepository, InMemorySightingRepository
    from .repository import BaseRouteRepository, PostgresRouteRepository, InMemoryRouteRepository
    from .pipeline import RouteEnginePipeline
except (ImportError, ValueError):
    import importlib
    models_m = importlib.import_module('07_route_engine.models')
    LocationQuality, TimeSource, TimeQuality, FeasibilityClass, TrajectoryStatus = models_m.LocationQuality, models_m.TimeSource, models_m.TimeQuality, models_m.FeasibilityClass, models_m.TrajectoryStatus
    CameraGeo, EventTimeInfo, RouteSighting, RouteSegment, TargetTrajectory, TrajectorySummary = models_m.CameraGeo, models_m.EventTimeInfo, models_m.RouteSighting, models_m.RouteSegment, models_m.TargetTrajectory, models_m.TrajectorySummary
    RouteEngineConfig = importlib.import_module('07_route_engine.config').RouteEngineConfig
    sp_m = importlib.import_module('07_route_engine.spatial')
    haversine_distance_m, validate_coordinates, calculate_segment_distance = sp_m.haversine_distance_m, sp_m.validate_coordinates, sp_m.calculate_segment_distance
    tm_m = importlib.import_module('07_route_engine.time_mapping')
    resolve_event_time_info, compute_segment_time_delta = tm_m.resolve_event_time_info, tm_m.compute_segment_time_delta
    evaluate_segment_feasibility = importlib.import_module('07_route_engine.feasibility').evaluate_segment_feasibility
    tr_m = importlib.import_module('07_route_engine.trajectory')
    solve_best_trajectory_dag, collapse_same_camera_dwell_sightings = tr_m.solve_best_trajectory_dag, tr_m.collapse_same_camera_dwell_sightings
    evaluate_trajectory_confidence_and_reasons = importlib.import_module('07_route_engine.confidence').evaluate_trajectory_confidence_and_reasons
    export_trajectory_to_geojson = importlib.import_module('07_route_engine.geojson').export_trajectory_to_geojson
    cr_m = importlib.import_module('07_route_engine.camera_repository')
    BaseCameraRepository, PostgresCameraRepository, InMemoryCameraRepository = cr_m.BaseCameraRepository, cr_m.PostgresCameraRepository, cr_m.InMemoryCameraRepository
    sr_m = importlib.import_module('07_route_engine.sighting_repository')
    SightingRepository, InMemorySightingRepository = sr_m.SightingRepository, sr_m.InMemorySightingRepository
    rr_m = importlib.import_module('07_route_engine.repository')
    BaseRouteRepository, PostgresRouteRepository, InMemoryRouteRepository = rr_m.BaseRouteRepository, rr_m.PostgresRouteRepository, rr_m.InMemoryRouteRepository
    RouteEnginePipeline = importlib.import_module('07_route_engine.pipeline').RouteEnginePipeline

__all__ = [
    'LocationQuality', 'TimeSource', 'TimeQuality', 'FeasibilityClass', 'TrajectoryStatus',
    'CameraGeo', 'EventTimeInfo', 'RouteSighting', 'RouteSegment', 'TargetTrajectory', 'TrajectorySummary',
    'RouteEngineConfig', 'haversine_distance_m', 'validate_coordinates', 'calculate_segment_distance',
    'resolve_event_time_info', 'compute_segment_time_delta', 'evaluate_segment_feasibility',
    'solve_best_trajectory_dag', 'collapse_same_camera_dwell_sightings',
    'evaluate_trajectory_confidence_and_reasons', 'export_trajectory_to_geojson',
    'BaseCameraRepository', 'PostgresCameraRepository', 'InMemoryCameraRepository',
    'SightingRepository', 'InMemorySightingRepository',
    'BaseRouteRepository', 'PostgresRouteRepository', 'InMemoryRouteRepository',
    'RouteEnginePipeline',
]
