from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .models import (
    TargetTrajectory,
    TrajectorySummary,
    TrajectoryStatus,
    RouteSighting,
    RouteSegment,
    CameraGeo
)
from .config import RouteEngineConfig
from .camera_repository import BaseCameraRepository, PostgresCameraRepository, InMemoryCameraRepository
from .sighting_repository import SightingRepository, InMemorySightingRepository
from .repository import BaseRouteRepository, PostgresRouteRepository, InMemoryRouteRepository
from .trajectory import solve_best_trajectory_dag
from .confidence import evaluate_trajectory_confidence_and_reasons
from .geojson import export_trajectory_to_geojson


class RouteEnginePipeline:
    """
    Main Service Pipeline for Priority 7 Spatio-Temporal Trajectory & Route Reconstruction.
    Directly consumable by Priority 8 REST API and Priority 9 Control Room Dashboard.
    """

    def __init__(
        self,
        config: Optional[RouteEngineConfig] = None,
        camera_repo: Optional[BaseCameraRepository] = None,
        sighting_repo: Optional[SightingRepository] = None,
        route_repo: Optional[BaseRouteRepository] = None
    ):
        self.config = config or RouteEngineConfig.from_yaml()
        self.camera_repo = camera_repo or PostgresCameraRepository()
        self.sighting_repo = sighting_repo or SightingRepository(camera_repo=self.camera_repo)
        self.route_repo = route_repo or PostgresRouteRepository()

    def build_target_trajectory(
        self,
        registration: str,
        start_time_utc: Optional[datetime] = None,
        end_time_utc: Optional[datetime] = None,
        min_match_score: Optional[float] = None,
        persist: bool = True
    ) -> TargetTrajectory:
        """
        Reconstructs the optimal spatiotemporal trajectory for a target vehicle registration.
        """
        norm_reg = registration.strip().upper().replace(' ', '').replace('-', '')
        threshold = min_match_score if min_match_score is not None else self.config.min_match_score

        # 1. Retrieve Candidate Sightings
        candidate_sightings = self.sighting_repo.get_target_sightings(
            registration=norm_reg,
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            min_match_score=threshold,
            limit=self.config.max_candidate_sightings
        )

        # 2. Retrieve All Camera Locations
        cameras_map = self.camera_repo.get_all_cameras()

        # Enforce camera coordinates on sightings if missing from join
        for s in candidate_sightings:
            if s.latitude is None and s.camera_id in cameras_map:
                cam = cameras_map[s.camera_id]
                s.latitude = cam.latitude
                s.longitude = cam.longitude
                s.azimuth = cam.azimuth
                s.location_quality = cam.location_quality

        # 3. Solve Optimal Trajectory DAG
        selected_sightings, segments, status, raw_conf, alt_paths, solve_warnings = solve_best_trajectory_dag(
            candidate_sightings=candidate_sightings,
            cameras_map=cameras_map,
            config=self.config
        )

        # 4. Multi-Factor Confidence & Explainability
        conf, reasons, conf_warnings = evaluate_trajectory_confidence_and_reasons(
            selected_sightings=selected_sightings,
            segments=segments,
            status=status,
            config=self.config
        )

        all_warnings = list(dict.fromkeys(solve_warnings + conf_warnings))

        # 5. Compute Aggregate Metrics
        total_dist_m = sum(seg.distance_lower_bound_m for seg in segments)
        start_t = selected_sightings[0].event_time_utc if selected_sightings else None
        end_t = selected_sightings[-1].event_time_utc if selected_sightings else None
        duration_s = max(0.0, (end_t - start_t).total_seconds()) if (start_t and end_t) else 0.0
        avg_speed_kmh = round((total_dist_m / max(duration_s, 1.0)) * 3.6, 2) if duration_s > 0 else 0.0

        # 6. Generate RFC-7946 GeoJSON
        geojson_doc = export_trajectory_to_geojson(
            target_id=norm_reg,
            registration=norm_reg,
            sightings=selected_sightings,
            segments=segments,
            confidence=conf,
            status=status,
            precision=self.config.decimal_precision
        )

        trajectory = TargetTrajectory(
            target_id=norm_reg,
            registration=norm_reg,
            sightings=selected_sightings,
            segments=segments,
            trajectory_confidence=conf,
            status=status,
            start_time_utc=start_t,
            end_time_utc=end_t,
            duration_seconds=duration_s,
            total_lower_bound_distance_m=total_dist_m,
            minimum_average_speed_kmh=avg_speed_kmh,
            geojson=geojson_doc,
            reasons=reasons,
            warnings=all_warnings,
            alternative_trajectories=alt_paths,
            created_at=datetime.now(timezone.utc)
        )

        # 7. Persistence
        if persist and self.route_repo:
            try:
                self.route_repo.save_trajectory_run(trajectory)
            except Exception as e:
                trajectory.warnings.append(f"Persistence warning: {e}")

        return trajectory

    def get_route_geojson(
        self,
        registration: str,
        start_time_utc: Optional[datetime] = None,
        end_time_utc: Optional[datetime] = None,
        min_match_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """Returns standard GeoJSON FeatureCollection directly for Leaflet / Mapbox."""
        traj = self.build_target_trajectory(
            registration=registration,
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            min_match_score=min_match_score,
            persist=False
        )
        return traj.geojson

    def get_nearby_cameras(
        self,
        latitude: float,
        longitude: float,
        radius_m: Optional[float] = None
    ) -> List[CameraGeo]:
        """Spatial radius query for nearby cameras using PostGIS ST_DWithin."""
        r = radius_m if radius_m is not None else self.config.default_nearby_radius_m
        return self.camera_repo.get_nearby_cameras(latitude, longitude, radius_m=r)

    def summarize_trajectory(self, trajectory: TargetTrajectory) -> TrajectorySummary:
        """Produces a compact summary model for API list endpoints."""
        cam_count = len(set(s.camera_id for s in trajectory.sightings))
        return TrajectorySummary(
            target_id=trajectory.target_id,
            registration=trajectory.registration,
            status=trajectory.status,
            trajectory_confidence=trajectory.trajectory_confidence,
            first_seen_utc=trajectory.start_time_utc,
            last_seen_utc=trajectory.end_time_utc,
            sighting_count=len(trajectory.sightings),
            camera_count=cam_count,
            total_lower_bound_distance_km=round(trajectory.total_lower_bound_distance_m / 1000.0, 2),
            minimum_average_speed_kmh=trajectory.minimum_average_speed_kmh,
            warnings_count=len(trajectory.warnings)
        )
