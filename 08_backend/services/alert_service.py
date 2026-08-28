import importlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from ..errors import AlertNotFoundError
    from ..schemas.alerts import AlertResponse, AlertAckResponse
except (ImportError, ValueError):
    AlertNotFoundError = importlib.import_module("08_backend.errors").AlertNotFoundError
    alt_m = importlib.import_module("08_backend.schemas.alerts")
    AlertResponse, AlertAckResponse = alt_m.AlertResponse, alt_m.AlertAckResponse


def _get_target_repo():
    p5_repo = importlib.import_module("05_target_matching.repository")
    return p5_repo.PostgresTargetMatchingRepository()


class AlertService:
    """Service managing real-time vehicle alerts and alert acknowledgement."""

    def __init__(self, repository=None):
        self.repository = repository or _get_target_repo()

    def query_alerts(
        self,
        unacknowledged_only: bool = False,
        camera_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AlertResponse]:
        raw_alerts = self.repository.query_alerts(
            unacknowledged_only=unacknowledged_only,
            camera_id=camera_id,
            limit=limit + offset
        )

        paged = raw_alerts[offset : offset + limit]
        return [
            AlertResponse(
                alert_id=a["alert_id"],
                watchlist_id=a["watchlist_id"],
                sighting_id=a["sighting_id"],
                camera_id=a["camera_id"],
                stream_epoch=a["stream_epoch"],
                track_id=a["track_id"],
                registration=a["registration"],
                match_score=a["match_score"],
                match_class=a["match_class"],
                severity=a["severity"],
                created_at=datetime.fromisoformat(a["created_at"]) if isinstance(a["created_at"], str) else a["created_at"],
                acknowledged=bool(a["acknowledged"]),
                acknowledged_by=a.get("acknowledged_by"),
                acknowledged_at=datetime.fromisoformat(a["acknowledged_at"]) if a.get("acknowledged_at") and isinstance(a["acknowledged_at"], str) else a.get("acknowledged_at"),
                explanation=a.get("explanation") or []
            )
            for a in paged
        ]

    def get_alert_by_id(self, alert_id: str) -> AlertResponse:
        alerts = self.query_alerts(unacknowledged_only=False, limit=1000)
        matching = [a for a in alerts if a.alert_id == alert_id]
        if not matching:
            raise AlertNotFoundError(f"Alert '{alert_id}' not found.")
        return matching[0]

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "operator") -> AlertAckResponse:
        conn = self.repository._get_connection()
        now = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE alerts SET acknowledged = TRUE, acknowledged_by = %s, acknowledged_at = %s WHERE alert_id = %s RETURNING alert_id;",
                (acknowledged_by, now, alert_id)
            )
            r = cur.fetchone()
        conn.commit()
        conn.close()

        if not r:
            raise AlertNotFoundError(f"Alert '{alert_id}' not found.")

        return AlertAckResponse(
            success=True,
            alert_id=alert_id,
            acknowledged=True,
            acknowledged_by=acknowledged_by,
            acknowledged_at=now
        )

    def get_alert_snapshot(self, alert_id: str) -> dict:
        """Captures snapshot of alert acknowledgment state for transactional compensation."""
        alert = self.get_alert_by_id(alert_id)
        return {
            "alert_id": alert.alert_id,
            "acknowledged": alert.acknowledged,
            "acknowledged_by": alert.acknowledged_by,
            "acknowledged_at": alert.acknowledged_at,
        }

    def restore_alert_snapshot(self, alert_id: str, snapshot: dict) -> None:
        """Restores alert acknowledgment state to prior snapshot on audit log failure."""
        conn = self.repository._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE alerts SET acknowledged = %s, acknowledged_by = %s, acknowledged_at = %s WHERE alert_id = %s;",
                (snapshot["acknowledged"], snapshot["acknowledged_by"], snapshot["acknowledged_at"], alert_id)
            )
        conn.commit()
        conn.close()

