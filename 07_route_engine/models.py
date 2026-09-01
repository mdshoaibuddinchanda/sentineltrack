from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, List, Dict


class LocationQuality(str, Enum):
    VERIFIED = 'VERIFIED'        # Exact GPS coordinates from survey/GIS
    APPROXIMATE = 'APPROXIMATE'  # Geocoded junction or landmark area
    UNKNOWN = 'UNKNOWN'          # Missing / unverified coordinates


class TimeSource(str, Enum):
    SOURCE_WALLCLOCK = 'SOURCE_WALLCLOCK'        # Camera ONVIF / NTP timestamp
    PTS_ANCHORED_ESTIMATE = 'PTS_ANCHORED_ESTIMATE' # Stable PTS offset from stream start UTC
    INGEST_TIME = 'INGEST_TIME'                  # Packet arrival at video decoder
    DB_PERSISTENCE_FALLBACK = 'DB_PERSISTENCE_FALLBACK' # Database row insertion timestamp
    UNKNOWN = 'UNKNOWN'


class TimeQuality(str, Enum):
    HIGH = 'HIGH'        # Hardware NTP / calibrated source clock
    MEDIUM = 'MEDIUM'    # Stable PTS anchored to ingest start
    LOW = 'LOW'          # Unanchored DB persistence timestamp fallback
    UNKNOWN = 'UNKNOWN'


class FeasibilityClass(str, Enum):
    FEASIBLE = 'FEASIBLE'          # Physically plausible speed & trajectory
    QUESTIONABLE = 'QUESTIONABLE'  # Marginal speed or low timing quality
    IMPOSSIBLE = 'IMPOSSIBLE'      # Exceeds physical speed limits (>220 km/h)
    UNKNOWN = 'UNKNOWN'            # Missing location or timestamp


class TrajectoryStatus(str, Enum):
    CONFIRMED_SEQUENCE = 'CONFIRMED_SEQUENCE'            # High-confidence, chronologically & physically consistent
    PLAUSIBLE_SEQUENCE = 'PLAUSIBLE_SEQUENCE'            # Physically plausible, moderate evidence
    AMBIGUOUS = 'AMBIGUOUS'                              # Multiple competing plausible trajectories
    CONFLICTING_SIGHTINGS = 'CONFLICTING_SIGHTINGS'      # High-confidence sightings with impossible transition
    SINGLE_SIGHTING = 'SINGLE_SIGHTING'                  # Only 1 observation (no route geometry)
    INSUFFICIENT_EVIDENCE = 'INSUFFICIENT_EVIDENCE'      # Insufficient score/observations
    NO_ROUTE = 'NO_ROUTE'                                # Zero sightings found


@dataclass
class CameraGeo:
    """Geospatial metadata for a camera sensor."""
    camera_id: str
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    azimuth: Optional[float] = None
    location_quality: LocationQuality = LocationQuality.VERIFIED
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_valid_coordinates(self) -> bool:
        if self.latitude is None or self.longitude is None:
            return False
        return -90.0 <= self.latitude <= 90.0 and -180.0 <= self.longitude <= 180.0


@dataclass
class EventTimeInfo:
    """Detailed timing provenance for a camera observation event."""
    source_pts_ms: float
    stream_epoch: int
    event_time_utc: datetime
    time_source: TimeSource = TimeSource.PTS_ANCHORED_ESTIMATE
    time_quality: TimeQuality = TimeQuality.MEDIUM
    ingest_time_utc: Optional[datetime] = None
    mapping_error_ms: float = 0.0


@dataclass
class RouteSighting:
    """Enriched vehicle observation node evaluated for trajectory reconstruction."""
    sighting_id: str
    target_id: Optional[str]
    registration_candidate: str
    camera_id: str
    stream_epoch: int
    track_id: int

    first_pts_ms: float
    last_pts_ms: float

    event_time_utc: datetime
    time_source: TimeSource = TimeSource.PTS_ANCHORED_ESTIMATE
    time_quality: TimeQuality = TimeQuality.MEDIUM

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    azimuth: Optional[float] = None
    location_quality: LocationQuality = LocationQuality.VERIFIED
    location_label: Optional[str] = None

    match_score: float = 1.0
    match_class: str = 'EXACT'
    ocr_confidence: float = 0.90
    support_count: int = 1

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteSegment:
    """Directed spatiotemporal transition edge between two sequential sightings."""
    from_sighting_id: str
    to_sighting_id: str
    from_camera_id: str
    to_camera_id: str

    from_time_utc: datetime
    to_time_utc: datetime

    distance_lower_bound_m: float
    delta_seconds: float
    minimum_required_speed_kmh: float

    feasibility: FeasibilityClass
    segment_score: float

    sequence_index: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class TargetTrajectory:
    """Complete reconstructed spatiotemporal vehicle trajectory."""
    target_id: str
    registration: str

    sightings: List[RouteSighting]
    segments: List[RouteSegment]

    trajectory_confidence: float
    status: TrajectoryStatus

    start_time_utc: Optional[datetime]
    end_time_utc: Optional[datetime]
    duration_seconds: float
    total_lower_bound_distance_m: float
    minimum_average_speed_kmh: float

    geojson: Dict[str, Any]
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    alternative_trajectories: List[Any] = field(default_factory=list)
    algorithm_version: str = '1.0.0'
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TrajectorySummary:
    """Compact summary for API responses and dashboard widgets."""
    target_id: str
    registration: str
    status: TrajectoryStatus
    trajectory_confidence: float
    first_seen_utc: Optional[datetime]
    last_seen_utc: Optional[datetime]
    sighting_count: int
    camera_count: int
    total_lower_bound_distance_km: float
    minimum_average_speed_kmh: float
    warnings_count: int
