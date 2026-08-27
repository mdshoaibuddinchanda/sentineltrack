import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from .models import (
    Alert,
    AlertSeverity,
    MatchCandidate,
    MatchClass,
    WatchlistEntry,
    WatchlistPriority
)
from .config import TargetMatchingConfig


def calculate_alert_severity(
    watchlist_priority: WatchlistPriority,
    match_class: MatchClass,
    match_score: float,
    is_weak_evidence: bool = False
) -> AlertSeverity:
    """Calculates operational alert severity based on watchlist urgency and match confidence."""
    if is_weak_evidence:
        return AlertSeverity.REVIEW

    if watchlist_priority == WatchlistPriority.CRITICAL:
        if match_class in (MatchClass.EXACT, MatchClass.HIGH_PROBABILITY):
            return AlertSeverity.CRITICAL
        return AlertSeverity.HIGH

    elif watchlist_priority == WatchlistPriority.HIGH:
        if match_class == MatchClass.EXACT:
            return AlertSeverity.CRITICAL
        elif match_class == MatchClass.HIGH_PROBABILITY:
            return AlertSeverity.HIGH
        return AlertSeverity.MEDIUM

    elif watchlist_priority == WatchlistPriority.NORMAL:
        if match_class == MatchClass.EXACT:
            return AlertSeverity.HIGH
        elif match_class == MatchClass.HIGH_PROBABILITY:
            return AlertSeverity.MEDIUM
        return AlertSeverity.REVIEW

    else:  # LOW
        if match_class == MatchClass.EXACT:
            return AlertSeverity.MEDIUM
        return AlertSeverity.LOW


class AlertManager:
    """
    Idempotent alert manager with track-level deduplication and evidence gating.
    Guarantees that a single vehicle track does not spam operators across multiple frames,
    while ensuring legitimate cross-camera vehicle detections are always captured.
    """

    def __init__(
        self,
        config: Optional[TargetMatchingConfig] = None,
        cooldown_seconds: Optional[float] = None,
        deduplicate_by_track: Optional[bool] = None,
        min_alert_class: Optional[str] = None
    ):
        self.config = config or TargetMatchingConfig.from_yaml()
        if cooldown_seconds is not None:
            self.config.cooldown_seconds = cooldown_seconds
        if deduplicate_by_track is not None:
            self.config.deduplicate_by_track = deduplicate_by_track
        if min_alert_class is not None:
            self.config.min_alert_class = min_alert_class

        self._lock = threading.Lock()

        # In-memory active alerts: alert_id -> Alert
        self._alerts: dict[str, Alert] = {}

        # Idempotency tracking: (camera_id, stream_epoch, track_id, watchlist_id) -> alert_id
        self._track_alerts: dict[tuple[str, int, int, str], str] = {}

        # Last alert timestamp per camera & target: (camera_id, watchlist_id) -> datetime
        self._cam_target_last_alert: dict[tuple[str, str], datetime] = {}

    def process_match(
        self,
        candidate: MatchCandidate,
        watchlist_entry: WatchlistEntry,
        sighting_id: str
    ) -> tuple[Optional[Alert], bool, str]:
        """
        Evaluates a match candidate against alert policies and idempotency state.
        Returns:
            tuple[alert: Optional[Alert], is_new_alert: bool, reason: str]
        """
        # 1. Minimum Match Class Filter
        if candidate.match_class == MatchClass.REJECTED or candidate.match_class == MatchClass.POSSIBLE:
            return None, False, f'Match class {candidate.match_class.value} does not meet alert threshold'

        if self.config.min_alert_class == 'HIGH_PROBABILITY' and candidate.match_class == MatchClass.PROBABLE:
            return None, False, 'Match class PROBABLE is retained for review queue, no immediate automatic alert'

        # 2. Exact Match Evidence Gating
        is_weak_evidence = False
        if candidate.match_class == MatchClass.EXACT and self.config.exact_evidence_gate_required:
            if candidate.multi_frame_support < self.config.min_exact_alert_support and candidate.ocr_confidence < self.config.min_exact_alert_confidence:
                is_weak_evidence = True

        track_key = (
            candidate.camera_id,
            candidate.stream_epoch,
            candidate.track_id,
            watchlist_entry.watchlist_id
        )
        cam_target_key = (candidate.camera_id, watchlist_entry.watchlist_id)
        now = datetime.now(timezone.utc)

        with self._lock:
            # 3. Track-Level Idempotency Check (Same camera, epoch, track_id)
            if self.config.deduplicate_by_track and track_key in self._track_alerts:
                existing_id = self._track_alerts[track_key]
                existing_alert = self._alerts.get(existing_id)
                if existing_alert:
                    # Update existing alert if this observation has a higher match score
                    if candidate.match_score > existing_alert.match_score:
                        existing_alert.match_score = candidate.match_score
                        existing_alert.match_class = candidate.match_class
                        existing_alert.explanation = candidate.reasons
                    return existing_alert, False, 'Updated existing alert for this vehicle track (idempotent)'

            # 4. Intra-Camera Cooldown Check (Only suppresses repeated alerts on SAME camera)
            last_alert_time = self._cam_target_last_alert.get(cam_target_key)
            if last_alert_time and (now - last_alert_time).total_seconds() < self.config.cooldown_seconds:
                if candidate.match_class != MatchClass.EXACT and watchlist_entry.priority != WatchlistPriority.CRITICAL:
                    return None, False, f'Alert cooldown active on camera {candidate.camera_id} for target {watchlist_entry.normalized_registration}'

            # 5. Generate New Actionable Alert
            severity = calculate_alert_severity(
                watchlist_entry.priority,
                candidate.match_class,
                candidate.match_score,
                is_weak_evidence=is_weak_evidence
            )
            alert_id = str(uuid.uuid4())
            alert = Alert(
                alert_id=alert_id,
                watchlist_id=watchlist_entry.watchlist_id,
                sighting_id=sighting_id,
                camera_id=candidate.camera_id,
                stream_epoch=candidate.stream_epoch,
                track_id=candidate.track_id,
                registration=candidate.observed_registration,
                match_score=candidate.match_score,
                match_class=candidate.match_class,
                severity=severity,
                created_at=now,
                explanation=candidate.reasons
            )

            self._alerts[alert_id] = alert
            self._track_alerts[track_key] = alert_id
            self._cam_target_last_alert[cam_target_key] = now

            return alert, True, 'New alert generated'

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        with self._lock:
            if alert_id not in self._alerts:
                return False
            alert = self._alerts[alert_id]
            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.now(timezone.utc)
            return True

    def get_alerts(
        self,
        unacknowledged_only: bool = False,
        min_severity: Optional[AlertSeverity] = None,
        camera_id: Optional[str] = None
    ) -> list[Alert]:
        with self._lock:
            res = []
            for a in self._alerts.values():
                if unacknowledged_only and a.acknowledged:
                    continue
                if camera_id and a.camera_id != camera_id:
                    continue
                res.append(a)
            return sorted(res, key=lambda x: x.created_at, reverse=True)
