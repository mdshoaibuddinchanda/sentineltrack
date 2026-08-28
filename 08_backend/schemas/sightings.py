from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SightingResponse(BaseModel):
    sighting_id: str
    camera_id: str
    stream_epoch: int
    track_id: int
    first_pts_ms: float
    last_pts_ms: float
    registration_candidate: str
    confidence: float
    match_score: float
    match_class: str
    target_id: Optional[str] = None
    created_at: datetime
    raw_evidence: Dict[str, Any] = Field(default_factory=dict)
    event_time_utc: Optional[datetime] = None
    event_time_source: Optional[str] = None
    event_time_quality: Optional[str] = None
    ingest_time_utc: Optional[datetime] = None


class SightingListResponse(BaseModel):
    items: List[SightingResponse]
    total: int


class VehicleHistoryResponse(BaseModel):
    registration: str
    normalized_registration: str
    total_sightings: int
    sightings: List[SightingResponse]
