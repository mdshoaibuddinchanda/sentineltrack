from typing import List, Tuple, Optional, Any
from .models import (
    RouteSighting,
    RouteSegment,
    TrajectoryStatus,
    FeasibilityClass,
    TimeQuality,
    LocationQuality
)
from .config import RouteEngineConfig


def evaluate_trajectory_confidence_and_reasons(
    selected_sightings: List[RouteSighting],
    segments: List[RouteSegment],
    status: TrajectoryStatus,
    config: Optional[Any] = None
) -> Tuple[float, List[str], List[str]]:
    """
    Computes weighted multi-factor trajectory confidence and produces explainable rationale.
    """
    reasons = []
    warnings = []

    if not selected_sightings:
        return 0.0, ["No sightings found."], ["Target vehicle has no recorded sightings."]

    if len(selected_sightings) == 1:
        s = selected_sightings[0]
        reasons.append(f"Single observation at camera '{s.camera_id}' with match score {s.match_score:.2f}.")
        return round(s.match_score * 0.70, 4), reasons, ["Single observation: trajectory cannot be verified across multiple cameras."]

    # 1. Identity Component
    mean_match_score = sum(s.match_score for s in selected_sightings) / len(selected_sightings)
    reasons.append(f"{len(selected_sightings)} chronological sightings with average target match score of {mean_match_score:.2f}.")

    # 2. Timing Component
    time_qualities = [s.time_quality for s in selected_sightings]
    if all(tq == TimeQuality.HIGH for tq in time_qualities):
        timing_score = 1.0
        reasons.append("All observation timestamps derived from high-precision camera source time.")
    elif all(tq in (TimeQuality.HIGH, TimeQuality.MEDIUM) for tq in time_qualities):
        timing_score = 0.85
        reasons.append("Observation timestamps anchored to video stream PTS capture time.")
    else:
        timing_score = 0.65
        warnings.append("One or more sightings rely on database persistence timestamp fallback.")

    # 3. Spatial Component
    loc_qualities = [s.location_quality for s in selected_sightings]
    if all(lq == LocationQuality.VERIFIED for lq in loc_qualities):
        spatial_score = 1.0
        reasons.append("All camera sensor geospatial coordinates are surveyed and verified.")
    elif any(lq == LocationQuality.UNKNOWN for lq in loc_qualities):
        spatial_score = 0.50
        warnings.append("One or more camera locations are unknown / missing GPS coordinates.")
    else:
        spatial_score = 0.80
        reasons.append("Camera coordinates include approximate junction geocoding.")

    # 4. Feasibility Component
    if segments:
        avg_speed = sum(seg.minimum_required_speed_kmh for seg in segments) / len(segments)
        has_impossible = any(seg.feasibility == FeasibilityClass.IMPOSSIBLE for seg in segments)
        has_questionable = any(seg.feasibility == FeasibilityClass.QUESTIONABLE for seg in segments)

        if has_impossible:
            feasibility_score = 0.0
            warnings.append("Trajectory contains physically impossible movement transitions.")
        elif has_questionable:
            feasibility_score = 0.65
            warnings.append("Trajectory contains high-speed transitions near physical plausibility limits.")
        else:
            feasibility_score = 1.0
            reasons.append(f"All inter-camera transitions are physically plausible (average lower-bound speed: {avg_speed:.1f} km/h).")
    else:
        feasibility_score = 1.0

    # Composite Weighted Confidence Score
    confidence = (
        mean_match_score * 0.40 +
        timing_score * 0.20 +
        spatial_score * 0.20 +
        feasibility_score * 0.20
    )

    for seg in segments:
        warnings.extend(seg.warnings)

    return round(confidence, 4), reasons, list(dict.fromkeys(warnings))
