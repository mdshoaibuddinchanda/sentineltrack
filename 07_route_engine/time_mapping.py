from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from .models import TimeSource, TimeQuality, EventTimeInfo, RouteSighting


def resolve_event_time_info(
    raw_sighting: dict,
    stream_start_utc: Optional[datetime] = None
) -> EventTimeInfo:
    """
    Determines true wall-clock event time and timing provenance from sighting fields.
    Never assumes raw stream PTS is comparable across cameras.
    """
    pts_ms = float(raw_sighting.get('first_pts_ms', 0.0))
    epoch = int(raw_sighting.get('stream_epoch', 1))
    created_at = raw_sighting.get('created_at')

    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except Exception:
            created_at = datetime.now(timezone.utc)
    elif not isinstance(created_at, datetime):
        created_at = datetime.now(timezone.utc)

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    # 1. Explicit event_time_utc provided
    if raw_sighting.get('event_time_utc'):
        ev_time = raw_sighting['event_time_utc']
        if isinstance(ev_time, str):
            ev_time = datetime.fromisoformat(ev_time.replace('Z', '+00:00'))
        if ev_time.tzinfo is None:
            ev_time = ev_time.replace(tzinfo=timezone.utc)

        source_str = raw_sighting.get('event_time_source', 'SOURCE_WALLCLOCK')
        quality_str = raw_sighting.get('event_time_quality', 'HIGH')

        return EventTimeInfo(
            source_pts_ms=pts_ms,
            stream_epoch=epoch,
            event_time_utc=ev_time,
            time_source=TimeSource(source_str) if source_str in TimeSource.__members__ else TimeSource.SOURCE_WALLCLOCK,
            time_quality=TimeQuality(quality_str) if quality_str in TimeQuality.__members__ else TimeQuality.HIGH,
            ingest_time_utc=raw_sighting.get('ingest_time_utc'),
            mapping_error_ms=0.0
        )

    # 2. PTS anchored to stream start UTC
    if stream_start_utc is not None and pts_ms >= 0:
        if stream_start_utc.tzinfo is None:
            stream_start_utc = stream_start_utc.replace(tzinfo=timezone.utc)
        ev_time = stream_start_utc + timedelta(milliseconds=pts_ms)
        return EventTimeInfo(
            source_pts_ms=pts_ms,
            stream_epoch=epoch,
            event_time_utc=ev_time,
            time_source=TimeSource.PTS_ANCHORED_ESTIMATE,
            time_quality=TimeQuality.MEDIUM,
            ingest_time_utc=created_at,
            mapping_error_ms=100.0
        )

    # 3. Fallback to DB persistence created_at
    return EventTimeInfo(
        source_pts_ms=pts_ms,
        stream_epoch=epoch,
        event_time_utc=created_at,
        time_source=TimeSource.DB_PERSISTENCE_FALLBACK,
        time_quality=TimeQuality.LOW,
        ingest_time_utc=created_at,
        mapping_error_ms=1000.0
    )


def compute_segment_time_delta(
    from_sighting: RouteSighting,
    to_sighting: RouteSighting,
    clock_skew_tolerance_s: float = 5.0
) -> Tuple[float, Optional[str]]:
    """
    Computes time delta between two sightings in seconds.
    Returns (delta_seconds, warning_message).
    """
    t1 = from_sighting.event_time_utc
    t2 = to_sighting.event_time_utc

    if t1.tzinfo is None:
        t1 = t1.replace(tzinfo=timezone.utc)
    if t2.tzinfo is None:
        t2 = t2.replace(tzinfo=timezone.utc)

    raw_delta = (t2 - t1).total_seconds()

    # Case A: Exact chronological order
    if raw_delta > 0:
        return round(raw_delta, 3), None

    # Case B: Near-simultaneous observations within clock skew tolerance
    if -clock_skew_tolerance_s <= raw_delta <= 0:
        # Same camera dwell or adjacent junction observation
        return 0.001, f"Sightings within clock skew tolerance ({raw_delta:.2f}s). Adjusted to minimum delta."

    # Case C: Backward in time
    return raw_delta, f"Negative time delta ({raw_delta:.2f}s): Sighting {to_sighting.sighting_id} appears before {from_sighting.sighting_id}."
