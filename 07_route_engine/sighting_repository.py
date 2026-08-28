import importlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from .models import (
    RouteSighting,
    TimeSource,
    TimeQuality,
    LocationQuality,
    CameraGeo
)
from .time_mapping import resolve_event_time_info
from .camera_repository import BaseCameraRepository


def get_default_connection():
    try:
        db_mod = importlib.import_module('00_foundation.registry.database')
        return db_mod.get_connection()
    except Exception:
        import psycopg
        return psycopg.connect('dbname=sentinel user=sentinel host=localhost port=5432')


class SightingRepository:
    """Queries and enriches historical vehicle sightings for route reconstruction."""

    def __init__(
        self,
        connection_factory=None,
        camera_repo: Optional[BaseCameraRepository] = None
    ):
        self._get_connection = connection_factory or get_default_connection
        self.camera_repo = camera_repo

    def get_target_sightings(
        self,
        registration: str,
        start_time_utc: Optional[datetime] = None,
        end_time_utc: Optional[datetime] = None,
        min_match_score: float = 0.60,
        limit: int = 500
    ) -> List[RouteSighting]:
        """
        Retrieves matching vehicle sightings from PostgreSQL database.
        """
        import re
        norm_reg = re.sub(r'[^A-Z0-9]', '', registration.strip().upper())
        query = """
            SELECT s.sighting_id, s.camera_id, s.stream_epoch, s.track_id,
                   s.first_pts_ms, s.last_pts_ms, s.registration_candidate,
                   s.confidence, s.match_score, s.match_class, s.target_id,
                   s.created_at, s.raw_evidence,
                   c.latitude, c.longitude, c.azimuth, c.location_quality,
                   s.event_time_utc, s.event_time_source, s.event_time_quality, s.ingest_time_utc
            FROM vehicle_sightings s
            LEFT JOIN cameras c ON s.camera_id = c.camera_id
            WHERE (s.registration_candidate = %s 
                   OR s.raw_evidence->>'target_registration' = %s 
                   OR s.raw_evidence->>'top_target' = %s
                   OR s.target_id = %s)
              AND s.match_score >= %s
        """
        params: List[Any] = [norm_reg, norm_reg, norm_reg, norm_reg, min_match_score]

        if start_time_utc:
            query += " AND COALESCE(s.event_time_utc, s.created_at) >= %s"
            params.append(start_time_utc)
        if end_time_utc:
            query += " AND COALESCE(s.event_time_utc, s.created_at) <= %s"
            params.append(end_time_utc)

        query += " ORDER BY COALESCE(s.event_time_utc, s.created_at) ASC LIMIT %s;"
        params.append(limit)

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    rows = cur.fetchall()

                    results: List[RouteSighting] = []
                    for r in rows:
                        s_id, c_id, ep, trk, f_pts, l_pts, cand, conf, sc, cls_name, t_id, cr_at, raw_ev, lat, lon, az, lq, ev_t, ev_src, ev_qual, ing_t = r

                        # Resolve true event time
                        time_info = resolve_event_time_info({
                            'first_pts_ms': f_pts,
                            'stream_epoch': ep,
                            'created_at': cr_at,
                            'event_time_utc': ev_t,
                            'event_time_source': ev_src,
                            'event_time_quality': ev_qual,
                            'ingest_time_utc': ing_t,
                            'raw_evidence': raw_ev or {}
                        })

                        # Location quality
                        loc_q = LocationQuality(lq) if lq and lq in LocationQuality.__members__ else (LocationQuality.VERIFIED if lat is not None else LocationQuality.UNKNOWN)

                        route_s = RouteSighting(
                            sighting_id=s_id,
                            target_id=t_id,
                            registration_candidate=cand,
                            camera_id=c_id,
                            stream_epoch=ep,
                            track_id=trk,
                            first_pts_ms=f_pts,
                            last_pts_ms=l_pts,
                            event_time_utc=time_info.event_time_utc,
                            time_source=time_info.time_source,
                            time_quality=time_info.time_quality,
                            latitude=lat,
                            longitude=lon,
                            azimuth=az,
                            location_quality=loc_q,
                            match_score=sc,
                            match_class=cls_name,
                            ocr_confidence=conf,
                            support_count=int(raw_ev.get('multi_frame_support', 1)) if raw_ev else 1,
                            created_at=cr_at,
                            raw_evidence=raw_ev or {}
                        )
                        results.append(route_s)

                    return results
        except Exception:
            return []


class InMemorySightingRepository:
    """Mock sighting repository for unit tests and in-memory execution."""
    def __init__(self, sightings: Optional[List[RouteSighting]] = None):
        self._sightings: List[RouteSighting] = list(sightings or [])

    def add_sighting(self, sighting: RouteSighting):
        self._sightings.append(sighting)

    def get_target_sightings(
        self,
        registration: str,
        start_time_utc: Optional[datetime] = None,
        end_time_utc: Optional[datetime] = None,
        min_match_score: float = 0.60,
        limit: int = 500
    ) -> List[RouteSighting]:
        norm = registration.strip().upper().replace(' ', '').replace('-', '')
        results = []
        for s in self._sightings:
            s_cand = s.registration_candidate.strip().upper().replace(' ', '').replace('-', '')
            if (s_cand == norm or s.target_id == norm) and s.match_score >= min_match_score:
                if start_time_utc and s.event_time_utc < start_time_utc:
                    continue
                if end_time_utc and s.event_time_utc > end_time_utc:
                    continue
                results.append(s)
                if len(results) >= limit:
                    break
        return results


PostgresSightingRepository = SightingRepository
