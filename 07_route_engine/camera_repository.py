import threading
import json
import importlib
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

from .models import CameraGeo, LocationQuality
from .spatial import haversine_distance_m


def get_default_connection():
    try:
        db_mod = importlib.import_module('00_foundation.registry.database')
        return db_mod.get_connection()
    except Exception:
        import psycopg
        return psycopg.connect('dbname=sentinel user=sentinel host=localhost port=5432')


class BaseCameraRepository:
    def get_camera(self, camera_id: str) -> Optional[CameraGeo]:
        raise NotImplementedError

    def get_all_cameras(self) -> Dict[str, CameraGeo]:
        raise NotImplementedError

    def get_nearby_cameras(self, latitude: float, longitude: float, radius_m: float = 5000.0) -> List[CameraGeo]:
        raise NotImplementedError

    def save_camera(self, camera: CameraGeo) -> bool:
        raise NotImplementedError


class PostgresCameraRepository(BaseCameraRepository):
    """
    PostgreSQL / PostGIS camera repository with in-memory caching and ST_DWithin spatial queries.
    """

    def __init__(self, connection_factory=None):
        self._get_connection = connection_factory or get_default_connection
        self._lock = threading.Lock()
        self._cache: Dict[str, CameraGeo] = {}
        self.refresh_cache()

    def refresh_cache(self) -> int:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT camera_id, name, latitude, longitude, azimuth, location_quality, raw_metadata
                        FROM cameras;
                    """)
                    rows = cur.fetchall()
                    with self._lock:
                        self._cache.clear()
                        for r in rows:
                            c_id, name, lat, lon, az, lq, meta = r
                            geo = CameraGeo(
                                camera_id=c_id,
                                name=name,
                                latitude=lat,
                                longitude=lon,
                                azimuth=az,
                                location_quality=LocationQuality(lq) if lq and lq in LocationQuality.__members__ else LocationQuality.VERIFIED,
                                metadata=meta or {}
                            )
                            self._cache[c_id] = geo
                        return len(self._cache)
        except Exception:
            return 0

    def get_camera(self, camera_id: str) -> Optional[CameraGeo]:
        with self._lock:
            if camera_id in self._cache:
                return self._cache[camera_id]
        # Direct DB fallback
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT camera_id, name, latitude, longitude, azimuth, location_quality, raw_metadata
                        FROM cameras WHERE camera_id = %s;
                    """, (camera_id,))
                    row = cur.fetchone()
                    if row:
                        c_id, name, lat, lon, az, lq, meta = row
                        geo = CameraGeo(
                            camera_id=c_id,
                            name=name,
                            latitude=lat,
                            longitude=lon,
                            azimuth=az,
                            location_quality=LocationQuality(lq) if lq and lq in LocationQuality.__members__ else LocationQuality.VERIFIED,
                            metadata=meta or {}
                        )
                        with self._lock:
                            self._cache[c_id] = geo
                        return geo
        except Exception:
            pass
        return None

    def get_all_cameras(self) -> Dict[str, CameraGeo]:
        with self._lock:
            if self._cache:
                return dict(self._cache)
        self.refresh_cache()
        with self._lock:
            return dict(self._cache)

    def get_nearby_cameras(self, latitude: float, longitude: float, radius_m: float = 5000.0) -> List[CameraGeo]:
        """Queries cameras within radius_m using PostGIS ST_DWithin on spatial geography index."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT camera_id, name, latitude, longitude, azimuth, location_quality, raw_metadata,
                               ST_Distance(location, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) AS distance_m
                        FROM cameras
                        WHERE location IS NOT NULL
                          AND ST_DWithin(location, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
                        ORDER BY distance_m ASC;
                    """, (longitude, latitude, longitude, latitude, radius_m))
                    rows = cur.fetchall()
                    results = []
                    for r in rows:
                        c_id, name, lat, lon, az, lq, meta, dist = r
                        results.append(CameraGeo(
                            camera_id=c_id,
                            name=name,
                            latitude=lat,
                            longitude=lon,
                            azimuth=az,
                            location_quality=LocationQuality(lq) if lq and lq in LocationQuality.__members__ else LocationQuality.VERIFIED,
                            metadata=meta or {}
                        ))
                    return results
        except Exception:
            # Fallback to Python haversine over in-memory cache
            all_cams = self.get_all_cameras()
            nearby = []
            for cam in all_cams.values():
                if cam.has_valid_coordinates:
                    d = haversine_distance_m(latitude, longitude, cam.latitude, cam.longitude)
                    if d <= radius_m:
                        nearby.append(cam)
            return nearby

    def save_camera(self, camera: CameraGeo) -> bool:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO cameras (camera_id, name, latitude, longitude, azimuth, location_quality, location, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, NOW())
                        ON CONFLICT (camera_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            latitude = EXCLUDED.latitude,
                            longitude = EXCLUDED.longitude,
                            azimuth = EXCLUDED.azimuth,
                            location_quality = EXCLUDED.location_quality,
                            location = EXCLUDED.location,
                            updated_at = NOW();
                    """, (
                        camera.camera_id,
                        camera.name,
                        camera.latitude,
                        camera.longitude,
                        camera.azimuth,
                        camera.location_quality.value if hasattr(camera.location_quality, 'value') else camera.location_quality,
                        camera.longitude,
                        camera.latitude
                    ))
                conn.commit()
            with self._lock:
                self._cache[camera.camera_id] = camera
            return True
        except Exception:
            return False


class InMemoryCameraRepository(BaseCameraRepository):
    """Fast in-memory mock repository for tests."""
    def __init__(self):
        self._cameras: Dict[str, CameraGeo] = {}

    def get_camera(self, camera_id: str) -> Optional[CameraGeo]:
        return self._cameras.get(camera_id)

    def get_all_cameras(self) -> Dict[str, CameraGeo]:
        return dict(self._cameras)

    def get_nearby_cameras(self, latitude: float, longitude: float, radius_m: float = 5000.0) -> List[CameraGeo]:
        nearby = []
        for cam in self._cameras.values():
            if cam.has_valid_coordinates:
                d = haversine_distance_m(latitude, longitude, cam.latitude, cam.longitude)
                if d <= radius_m:
                    nearby.append(cam)
        return nearby

    def save_camera(self, camera: CameraGeo) -> bool:
        self._cameras[camera.camera_id] = camera
        return True
