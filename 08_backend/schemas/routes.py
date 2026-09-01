from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RouteSegmentResponse(BaseModel):
    segment_id: str
    sequence_index: int
    from_sighting_id: str
    to_sighting_id: str
    from_camera_id: str
    to_camera_id: str
    distance_lower_bound_m: float
    delta_seconds: float
    minimum_required_speed_kmh: float
    feasibility: str
    segment_score: float
    warnings: List[str] = Field(default_factory=list)


class RouteSightingResponse(BaseModel):
    sighting_id: str
    camera_id: str
    location_label: Optional[str] = None
    event_time_utc: datetime
    time_source: str
    time_quality: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_quality: str
    match_score: float


class RouteResponse(BaseModel):
    target_id: str
    registration: str
    status: str
    trajectory_confidence: float
    start_time_utc: Optional[datetime] = None
    end_time_utc: Optional[datetime] = None
    duration_seconds: float = 0.0
    total_lower_bound_distance_m: float = 0.0
    minimum_average_speed_kmh: float = 0.0
    sighting_count: int = 0
    camera_count: int = 0
    sightings: List[RouteSightingResponse] = Field(default_factory=list)
    segments: List[RouteSegmentResponse] = Field(default_factory=list)
    alternative_trajectories_count: int = 0
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    disclaimer: str = (
        "LineString connects observed camera sightings in chronological order. "
        "It does NOT represent a reconstructed road-level polyline."
    )


class RouteSummaryResponse(BaseModel):
    registration: str
    status: str
    confidence: float
    total_distance_km: float
    duration_minutes: float
    avg_speed_kmh: float
    sighting_count: int
    camera_count: int
    reasons: List[str]
    warnings: List[str]
    disclaimer: str = "Observed camera observation trajectory only."


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[Dict[str, Any]]
    properties: Dict[str, Any] = Field(default_factory=dict)
