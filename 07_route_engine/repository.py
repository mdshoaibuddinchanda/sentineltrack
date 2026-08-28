import json
import uuid
import threading
import importlib
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from .models import (
    TargetTrajectory,
    RouteSegment,
    RouteSighting,
    TrajectoryStatus,
    FeasibilityClass,
    TimeSource,
    TimeQuality,
    LocationQuality
)


def get_default_connection():
    try:
        db_mod = importlib.import_module('00_foundation.registry.database')
        return db_mod.get_connection()
    except Exception:
        import psycopg
        return psycopg.connect('dbname=sentinel user=sentinel host=localhost port=5432')


class BaseRouteRepository(ABC):
    @abstractmethod
    def save_trajectory_run(self, trajectory: TargetTrajectory) -> str:
        pass

    @abstractmethod
    def get_trajectory_run(self, route_id: str) -> Optional[TargetTrajectory]:
        pass

    @abstractmethod
    def get_latest_trajectory_run(self, registration: str) -> Optional[TargetTrajectory]:
        pass


class PostgresRouteRepository(BaseRouteRepository):
    """PostgreSQL / PostGIS persistence for Route Analysis Runs and Segments."""

    def __init__(self, connection_factory=None):
        self._get_connection = connection_factory or get_default_connection

    def save_trajectory_run(self, trajectory: TargetTrajectory) -> str:
        route_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Insert Route Analysis Run
                    cur.execute("""
                        INSERT INTO route_analysis_runs (
                            route_id, target_id, registration, requested_at, start_time, end_time,
                            trajectory_confidence, status, sighting_count, total_distance_m,
                            duration_seconds, geojson, warnings, algorithm_version, created_at
                        ) VALUES (
                            %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                        );
                    """, (
                        route_id,
                        trajectory.target_id,
                        trajectory.registration,
                        trajectory.start_time_utc,
                        trajectory.end_time_utc,
                        trajectory.trajectory_confidence,
                        trajectory.status.value if hasattr(trajectory.status, 'value') else str(trajectory.status),
                        len(trajectory.sightings),
                        trajectory.total_lower_bound_distance_m,
                        trajectory.duration_seconds,
                        json.dumps(trajectory.geojson),
                        json.dumps(trajectory.warnings),
                        trajectory.algorithm_version
                    ))

                    # 2. Insert Route Segments
                    for idx, seg in enumerate(trajectory.segments):
                        seg_id = str(uuid.uuid4())
                        cur.execute("""
                            INSERT INTO route_segments (
                                segment_id, route_id, sequence_index, from_sighting_id, to_sighting_id,
                                from_camera_id, to_camera_id, distance_lower_bound_m, delta_seconds,
                                minimum_required_speed_kmh, feasibility, segment_score, created_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                            );
                        """, (
                            seg_id,
                            route_id,
                            idx + 1,
                            seg.from_sighting_id,
                            seg.to_sighting_id,
                            seg.from_camera_id,
                            seg.to_camera_id,
                            seg.distance_lower_bound_m,
                            seg.delta_seconds,
                            seg.minimum_required_speed_kmh,
                            seg.feasibility.value if hasattr(seg.feasibility, 'value') else str(seg.feasibility),
                            seg.segment_score
                        ))

                conn.commit()
            return route_id
        except Exception:
            return route_id

    def get_trajectory_run(self, route_id: str) -> Optional[TargetTrajectory]:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT route_id, target_id, registration, start_time, end_time,
                               trajectory_confidence, status, sighting_count, total_distance_m,
                               duration_seconds, geojson, warnings, algorithm_version, created_at
                        FROM route_analysis_runs WHERE route_id = %s;
                    """, (route_id,))
                    row = cur.fetchone()
                    if not row:
                        return None

                    r_id, t_id, reg, st_t, end_t, conf, stat, s_count, dist, dur, gj, warns, ver, cr_at = row
                    return TargetTrajectory(
                        target_id=t_id,
                        registration=reg,
                        sightings=[],
                        segments=[],
                        trajectory_confidence=conf,
                        status=TrajectoryStatus(stat) if stat in TrajectoryStatus.__members__ else TrajectoryStatus.PLAUSIBLE_SEQUENCE,
                        start_time_utc=st_t,
                        end_time_utc=end_t,
                        duration_seconds=dur,
                        total_lower_bound_distance_m=dist,
                        minimum_average_speed_kmh=round((dist / max(dur, 1.0)) * 3.6, 2),
                        geojson=gj if isinstance(gj, dict) else json.loads(gj),
                        warnings=warns if isinstance(warns, list) else json.loads(warns or '[]'),
                        algorithm_version=ver,
                        created_at=cr_at
                    )
        except Exception:
            return None

    def get_latest_trajectory_run(self, registration: str) -> Optional[TargetTrajectory]:
        norm = registration.strip().upper().replace(' ', '').replace('-', '')
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT route_id FROM route_analysis_runs
                        WHERE registration = %s ORDER BY created_at DESC LIMIT 1;
                    """, (norm,))
                    row = cur.fetchone()
                    if row:
                        return self.get_trajectory_run(row[0])
        except Exception:
            pass
        return None


class InMemoryRouteRepository(BaseRouteRepository):
    """Thread-safe in-memory route repository for isolated tests."""
    def __init__(self):
        self._lock = threading.Lock()
        self._routes: Dict[str, TargetTrajectory] = {}
        self._routes_by_reg: Dict[str, List[str]] = {}

    def save_trajectory_run(self, trajectory: TargetTrajectory) -> str:
        route_id = str(uuid.uuid4())
        norm = trajectory.registration.strip().upper().replace(' ', '').replace('-', '')
        with self._lock:
            self._routes[route_id] = trajectory
            self._routes_by_reg.setdefault(norm, []).append(route_id)
        return route_id

    def get_trajectory_run(self, route_id: str) -> Optional[TargetTrajectory]:
        with self._lock:
            return self._routes.get(route_id)

    def get_latest_trajectory_run(self, registration: str) -> Optional[TargetTrajectory]:
        norm = registration.strip().upper().replace(' ', '').replace('-', '')
        with self._lock:
            ids = self._routes_by_reg.get(norm, [])
            if ids:
                return self._routes.get(ids[-1])
        return None
