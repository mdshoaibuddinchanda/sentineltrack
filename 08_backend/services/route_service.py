import time
import importlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from ..errors import RoutePersistenceAPIError
    from ..schemas.routes import RouteResponse, RouteSegmentResponse, RouteSightingResponse, RouteSummaryResponse, GeoJSONFeatureCollection
except (ImportError, ValueError):
    RoutePersistenceAPIError = importlib.import_module("08_backend.errors").RoutePersistenceAPIError
    rt_m = importlib.import_module("08_backend.schemas.routes")
    RouteResponse, RouteSegmentResponse, RouteSightingResponse, RouteSummaryResponse, GeoJSONFeatureCollection = rt_m.RouteResponse, rt_m.RouteSegmentResponse, rt_m.RouteSightingResponse, rt_m.RouteSummaryResponse, rt_m.GeoJSONFeatureCollection


def _get_route_pipeline():
    p7_pipe = importlib.import_module("07_route_engine.pipeline")
    return p7_pipe.RouteEnginePipeline()


class RouteService:
    """Service computing kinematic vehicle trajectories, summaries, and RFC-7946 GeoJSON with bounded caching."""

    def __init__(self, pipeline=None, cache_ttl_s: float = 5.0):
        self.pipeline = pipeline or _get_route_pipeline()
        self.cache_ttl_s = cache_ttl_s
        self._trajectory_cache: Dict[Tuple, Tuple[float, Any]] = {}

    def invalidate_cache(self, registration: Optional[str] = None) -> None:
        """Invalidates cached trajectory records globally or for a specific registration."""
        if registration is None:
            self._trajectory_cache.clear()
        else:
            reg_clean = registration.strip().upper()
            keys_to_remove = [k for k in self._trajectory_cache if k[0] == reg_clean]
            for k in keys_to_remove:
                self._trajectory_cache.pop(k, None)

    def build_target_trajectory(
        self,
        registration: str,
        start_time_utc: Optional[datetime] = None,
        end_time_utc: Optional[datetime] = None,
        min_match_score: float = 0.60,
        persist: bool = True
    ) -> RouteResponse:
        cache_key = (
            registration.strip().upper(),
            start_time_utc.isoformat() if start_time_utc else None,
            end_time_utc.isoformat() if end_time_utc else None,
            round(min_match_score, 2),
            persist
        )
        now = time.time()
        if cache_key in self._trajectory_cache:
            ts, cached_resp = self._trajectory_cache[cache_key]
            if (now - ts) < self.cache_ttl_s:
                return cached_resp

        try:
            traj = self.pipeline.build_target_trajectory(
                registration=registration,
                start_time_utc=start_time_utc,
                end_time_utc=end_time_utc,
                min_match_score=min_match_score,
                persist=persist
            )
        except Exception as e:
            if "RoutePersistenceError" in type(e).__name__:
                raise RoutePersistenceAPIError(f"Database persistence failure while computing trajectory: {e}")
            raise


        sightings_res = [
            RouteSightingResponse(
                sighting_id=s.sighting_id,
                camera_id=s.camera_id,
                event_time_utc=s.event_time_utc,
                time_source=s.time_source.value if hasattr(s.time_source, "value") else str(s.time_source),
                time_quality=s.time_quality.value if hasattr(s.time_quality, "value") else str(s.time_quality),
                latitude=s.latitude,
                longitude=s.longitude,
                location_quality=s.location_quality.value if hasattr(s.location_quality, "value") else str(s.location_quality),
                match_score=s.match_score
            )
            for s in traj.sightings
        ]

        segments_res = [
            RouteSegmentResponse(
                segment_id=getattr(seg, "segment_id", f"{seg.from_sighting_id}_{seg.to_sighting_id}"),
                sequence_index=seg.sequence_index,
                from_sighting_id=seg.from_sighting_id,
                to_sighting_id=seg.to_sighting_id,
                from_camera_id=seg.from_camera_id,
                to_camera_id=seg.to_camera_id,
                distance_lower_bound_m=seg.distance_lower_bound_m,
                delta_seconds=seg.delta_seconds,
                minimum_required_speed_kmh=seg.minimum_required_speed_kmh,
                feasibility=seg.feasibility.value if hasattr(seg.feasibility, "value") else str(seg.feasibility),
                segment_score=seg.segment_score,
                warnings=seg.warnings
            )
            for seg in traj.segments
        ]

        unique_cameras = len(set(s.camera_id for s in traj.sightings))

        return RouteResponse(
            target_id=traj.target_id,
            registration=traj.registration,
            status=traj.status.value if hasattr(traj.status, "value") else str(traj.status),
            trajectory_confidence=traj.trajectory_confidence,
            start_time_utc=traj.start_time_utc,
            end_time_utc=traj.end_time_utc,
            duration_seconds=traj.duration_seconds,
            total_lower_bound_distance_m=traj.total_lower_bound_distance_m,
            minimum_average_speed_kmh=traj.minimum_average_speed_kmh,
            sighting_count=len(traj.sightings),
            camera_count=unique_cameras,
            sightings=sightings_res,
            segments=segments_res,
            alternative_trajectories_count=len(traj.alternative_trajectories),
            reasons=traj.reasons,
            warnings=traj.warnings
        )

    def get_route_geojson(
        self,
        registration: str,
        start_time_utc: Optional[datetime] = None,
        end_time_utc: Optional[datetime] = None,
        min_match_score: float = 0.60
    ) -> Dict[str, Any]:
        return self.pipeline.get_route_geojson(
            registration=registration,
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            min_match_score=min_match_score
        )

    def get_route_summary(
        self,
        registration: str,
        start_time_utc: Optional[datetime] = None,
        end_time_utc: Optional[datetime] = None,
        min_match_score: float = 0.60
    ) -> RouteSummaryResponse:
        traj = self.pipeline.build_target_trajectory(
            registration=registration,
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            min_match_score=min_match_score,
            persist=False
        )
        unique_cameras = len(set(s.camera_id for s in traj.sightings))
        return RouteSummaryResponse(
            registration=traj.registration,
            status=traj.status.value if hasattr(traj.status, "value") else str(traj.status),
            confidence=traj.trajectory_confidence,
            total_distance_km=round(traj.total_lower_bound_distance_m / 1000.0, 2),
            duration_minutes=round(traj.duration_seconds / 60.0, 2),
            avg_speed_kmh=round(traj.minimum_average_speed_kmh, 1),
            sighting_count=len(traj.sightings),
            camera_count=unique_cameras,
            reasons=traj.reasons,
            warnings=traj.warnings
        )
