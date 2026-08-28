import importlib
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from ..schemas.sightings import SightingResponse, VehicleHistoryResponse
except (ImportError, ValueError):
    sight_m = importlib.import_module("08_backend.schemas.sightings")
    SightingResponse, VehicleHistoryResponse = sight_m.SightingResponse, sight_m.VehicleHistoryResponse


def _get_target_repo():
    p5_repo = importlib.import_module("05_target_matching.repository")
    return p5_repo.PostgresTargetMatchingRepository()


class SightingService:
    """Service querying vehicle observations and historical sightings."""

    def __init__(self, repository=None):
        self.repository = repository or _get_target_repo()

    def query_sightings(
        self,
        registration_pattern: Optional[str] = None,
        camera_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        min_score: float = 0.0,
        limit: int = 50,
        offset: int = 0
    ) -> List[SightingResponse]:
        raw_results = self.repository.query_sightings(
            registration_pattern=registration_pattern,
            camera_id=camera_id,
            created_after=start_time,
            created_before=end_time,
            min_score=min_score,
            limit=limit + offset
        )

        paged = raw_results[offset : offset + limit]
        return [
            SightingResponse(
                sighting_id=r["sighting_id"],
                camera_id=r["camera_id"],
                stream_epoch=r["stream_epoch"],
                track_id=r["track_id"],
                first_pts_ms=r["first_pts_ms"],
                last_pts_ms=r["last_pts_ms"],
                registration_candidate=r["registration_candidate"],
                confidence=r["confidence"],
                match_score=r["match_score"],
                match_class=r["match_class"],
                target_id=r.get("target_id"),
                created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
                raw_evidence=r.get("raw_evidence") or {},
                event_time_utc=datetime.fromisoformat(r["event_time_utc"]) if r.get("event_time_utc") and isinstance(r["event_time_utc"], str) else r.get("event_time_utc"),
                event_time_source=r.get("event_time_source"),
                event_time_quality=r.get("event_time_quality"),
                ingest_time_utc=datetime.fromisoformat(r["ingest_time_utc"]) if r.get("ingest_time_utc") and isinstance(r["ingest_time_utc"], str) else r.get("ingest_time_utc")
            )
            for r in paged
        ]

    def get_vehicle_history(
        self,
        registration: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> VehicleHistoryResponse:
        import re
        norm_reg = re.sub(r"[^A-Z0-9]", "", registration.upper())
        sightings = self.query_sightings(
            registration_pattern=norm_reg,
            start_time=start_time,
            end_time=end_time,
            min_score=0.0,
            limit=limit,
            offset=0
        )
        return VehicleHistoryResponse(
            registration=registration,
            normalized_registration=norm_reg,
            total_sightings=len(sightings),
            sightings=sightings
        )
