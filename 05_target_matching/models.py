from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
from enum import Enum


class MatchClass(str, Enum):
    EXACT = 'EXACT'
    HIGH_PROBABILITY = 'HIGH_PROBABILITY'
    PROBABLE = 'PROBABLE'
    POSSIBLE = 'POSSIBLE'
    REJECTED = 'REJECTED'


class WatchlistPriority(str, Enum):
    CRITICAL = 'CRITICAL'
    HIGH = 'HIGH'
    NORMAL = 'NORMAL'
    LOW = 'LOW'


class AlertSeverity(str, Enum):
    CRITICAL = 'CRITICAL'
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'
    REVIEW = 'REVIEW'


@dataclass
class TargetRegistration:
    """Represents a police/operator designated target vehicle registration."""
    target_id: str
    registration: str
    normalized_registration: str
    priority: WatchlistPriority = WatchlistPriority.NORMAL
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    notes: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchCandidate:
    """Detailed target-matching evaluation record for a single observation/track."""
    target_id: str
    target_registration: str
    observed_registration: str
    camera_id: str
    stream_epoch: int
    track_id: int
    first_pts_ms: float
    last_pts_ms: float

    raw_distance: int
    normalized_distance: float
    confusion_distance: float

    ocr_confidence: float
    crop_quality: float
    grammar_score: float
    multi_frame_support: int

    exact_match: bool
    match_score: float
    match_class: MatchClass

    matched_from: str = 'BEST_TEXT'  # 'BEST_TEXT' | 'ALTERNATIVE'
    alternative_rank: int = 0
    alternative_support_score: float = 1.0

    reasons: list[str] = field(default_factory=list)
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    reid_score: Optional[float] = None  # Reserved for Priority 6
    event_time_utc: Optional[datetime] = None
    event_time_source: Optional[str] = None
    event_time_quality: Optional[str] = None
    ingest_time_utc: Optional[datetime] = None


@dataclass
class Sighting:
    """Persisted vehicle observation record preserving raw OCR evidence for future rescoring."""
    sighting_id: str
    camera_id: str
    stream_epoch: int
    track_id: int
    first_pts_ms: float
    last_pts_ms: float
    registration_candidate: str
    confidence: float
    match_score: float
    match_class: MatchClass
    target_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_evidence: dict[str, Any] = field(default_factory=dict)
    event_time_utc: Optional[datetime] = None
    event_time_source: Optional[str] = None
    event_time_quality: Optional[str] = None
    ingest_time_utc: Optional[datetime] = None


@dataclass
class TargetMatchRecord:
    """Persisted record of an evaluated target candidate in target_matches table."""
    match_id: str
    sighting_id: str
    watchlist_id: str
    match_score: float
    match_class: MatchClass
    raw_distance: int
    confusion_distance: float
    matched_from: str = 'BEST_TEXT'
    alternative_rank: int = 0
    explanation: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class WatchlistEntry:
    """Active watchlist entity with precomputed indexing metadata."""
    watchlist_id: str
    registration: str
    normalized_registration: str
    priority: WatchlistPriority = WatchlistPriority.NORMAL
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Precomputed index properties
    state_prefix: str = ''
    rto_code: str = ''
    plate_length: int = 0

    def __post_init__(self):
        if self.normalized_registration:
            self.plate_length = len(self.normalized_registration)
            if self.plate_length >= 2:
                self.state_prefix = self.normalized_registration[:2]
            if self.plate_length >= 4:
                self.rto_code = self.normalized_registration[:4]


@dataclass
class Alert:
    """Actionable alert generated when an observation matches a watchlist entry."""
    alert_id: str
    watchlist_id: str
    sighting_id: str
    camera_id: str
    stream_epoch: int
    track_id: int
    registration: str
    match_score: float
    match_class: MatchClass
    severity: AlertSeverity
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    explanation: list[str] = field(default_factory=list)
