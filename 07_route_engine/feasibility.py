from typing import Tuple, List, Optional, Any
from .models import (
    RouteSighting,
    RouteSegment,
    FeasibilityClass,
    LocationQuality,
    TimeQuality
)
from .config import RouteEngineConfig
from .spatial import calculate_segment_distance
from .time_mapping import compute_segment_time_delta


def evaluate_segment_feasibility(
    from_sighting: RouteSighting,
    to_sighting: RouteSighting,
    from_cam_geo: Optional[Any] = None,
    to_cam_geo: Optional[Any] = None,
    config: Optional[RouteEngineConfig] = None
) -> RouteSegment:
    """
    Evaluates physical movement feasibility between two chronological sightings.
    Computes lower-bound distance and minimum required speed.
    """
    cfg = config or RouteEngineConfig.from_yaml()
    warnings = []

    # 1. Compute Distance Lower Bound
    dist_m, loc_qual = calculate_segment_distance(from_cam_geo, to_cam_geo)

    # 2. Compute Time Delta
    delta_s, time_warn = compute_segment_time_delta(
        from_sighting,
        to_sighting,
        clock_skew_tolerance_s=cfg.clock_skew_tolerance_seconds
    )
    if time_warn:
        warnings.append(time_warn)

    # 3. Calculate Required Speed Lower Bound
    if delta_s <= 0:
        req_speed_kmh = float('inf')
        feasibility = FeasibilityClass.IMPOSSIBLE
        segment_score = 0.0
        warnings.append(f"Non-positive delta_seconds ({delta_s:.2f}s) implies impossible backwards transition.")
    elif loc_qual == LocationQuality.UNKNOWN or from_sighting.time_quality == TimeQuality.UNKNOWN or to_sighting.time_quality == TimeQuality.UNKNOWN:
        req_speed_kmh = 0.0
        feasibility = FeasibilityClass.UNKNOWN
        segment_score = 0.40
        warnings.append("Unknown camera location or timing quality prevents definitive feasibility assessment.")
    elif dist_m == 0.0:
        req_speed_kmh = 0.0
        feasibility = FeasibilityClass.FEASIBLE
        segment_score = 1.0
    else:
        req_speed_kmh = round((dist_m / delta_s) * 3.6, 2)

        # Apply soft / highway speed threshold depending on distance
        soft_speed = cfg.highway_soft_speed_kmh if dist_m >= 10000.0 else cfg.urban_soft_speed_kmh

        if req_speed_kmh > cfg.hard_max_speed_kmh:
            feasibility = FeasibilityClass.IMPOSSIBLE
            segment_score = 0.0
            warnings.append(f"Minimum required speed ({req_speed_kmh:.1f} km/h) exceeds physical limit ({cfg.hard_max_speed_kmh} km/h).")
        elif req_speed_kmh > soft_speed:
            feasibility = FeasibilityClass.QUESTIONABLE
            # Graded penalty for high speed
            penalty_ratio = (req_speed_kmh - soft_speed) / (cfg.hard_max_speed_kmh - soft_speed)
            segment_score = max(0.20, 1.0 - penalty_ratio * 0.70)
            warnings.append(f"High required speed ({req_speed_kmh:.1f} km/h) exceeds soft threshold ({soft_speed} km/h).")
        else:
            feasibility = FeasibilityClass.FEASIBLE
            segment_score = 1.0

    # Timing quality adjustments
    if from_sighting.time_quality == TimeQuality.LOW or to_sighting.time_quality == TimeQuality.LOW:
        segment_score *= 0.85
        if feasibility == FeasibilityClass.FEASIBLE:
            warnings.append("Segment timing uses low-precision DB persistence fallback.")

    # Check for large time gap
    if delta_s > cfg.large_gap_seconds:
        warnings.append(f"Large time gap ({delta_s / 3600.0:.1f} hours) between sightings reduces continuous tracking certainty.")
        segment_score *= 0.80

    return RouteSegment(
        from_sighting_id=from_sighting.sighting_id,
        to_sighting_id=to_sighting.sighting_id,
        from_camera_id=from_sighting.camera_id,
        to_camera_id=to_sighting.camera_id,
        from_time_utc=from_sighting.event_time_utc,
        to_time_utc=to_sighting.event_time_utc,
        distance_lower_bound_m=dist_m,
        delta_seconds=max(0.001, delta_s),
        minimum_required_speed_kmh=req_speed_kmh,
        feasibility=feasibility,
        segment_score=round(segment_score, 4),
        warnings=warnings
    )
