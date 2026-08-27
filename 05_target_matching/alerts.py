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


def calculate_alert_severity(
    watchlist_priority: WatchlistPriority,
    match_class: MatchClass,
    match_score: float
) -> AlertSeverity:
    """Calculates operational alert severity based on watchlist urgency and match confidence."""
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
    Idempotent alert manager with track-level deduplication and cooldown policies.
    Guarantees that a single tracked vehicle does not spam police operators across multiple video frames.
    """

    def __init__(
        self,
        cooldown_seconds: float = 60.0,
        min_alert_class: MatchClass = MatchClass.HIGH_PROBABILITY
    ):
        self._lock = threading.Lock()
        self.cooldown_seconds = cooldown_seconds
        self.min_alert_class = min_alert_class

        # In-memory active alerts: alert_id -> Alert
        self._alerts: dict[str, Alert] = {}

        # Idempotency tracking: (camera_id, stream_epoch, track_id, watchlist_id) -> alert_id
        self._track_alerts: dict[tuple[str, int, int, str], str] = {}

        # Cooldown tracking: watchlist_id -> last_alert_time
        self._target_last_alert: dict[str, datetime] = {}

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
        # 1. Check if match class meets minimum alert threshold
        if candidate.match_class == MatchClass.REJECTED or candidate.match_class == MatchClass.POSSIBLE:
            return None, False, f'Match class {candidate.match_class.value} does not meet alert threshold'

        if self.min_alert_class == MatchClass.HIGH_PROBABILITY and candidate.match_class == MatchClass.PROBABLE:
            return None, False, 'Match class PROBABLE is retained for review, no immediate automatic alert'

        track_key = (
            candidate.camera_id,
            candidate.stream_epoch,
            candidate.track_id,
            watchlist_entry.watchlist_id
        )

        now = datetime.now(timezone.utc)

        with self._lock:
            # 2. Check Track-Level Idempotency
            if track_key in self._track_alerts:
                existing_id = self._track_alerts[track_key]
                existing_alert = self._alerts.get(existing_id)
                if existing_alert:
                    # Update existing alert if this observation has a higher match score
                    if candidate.match_score > existing_alert.match_score:
                        existing_alert.match_score = candidate.match_score
                        existing_alert.match_class = candidate.match_class
                        existing_alert.explanation = candidate.reasons
                    return existing_alert, False, 'Updated existing alert for this vehicle track (idempotent)'

            # 3. Check Cooldown Window (Across streams for same target)
            last_alert_time = self._target_last_alert.get(watchlist_entry.watchlist_id)
            if last_alert_time and (now - last_alert_time).total_seconds() < self.cooldown_seconds:
                # Still allow critical/exact matches to bypass cooldown
                if candidate.match_class != MatchClass.EXACT and watchlist_entry.priority != WatchlistPriority.CRITICAL:
                    return None, False, f'Alert cooldown active for target {watchlist_entry.normalized_registration}'

            # 4. Generate New Actionable Alert
            severity = calculate_alert_severity(
                watchlist_entry.priority,
                candidate.match_class,
                candidate.match_score
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
            self._target_last_alert[watchlist_entry.watchlist_id] = now

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
