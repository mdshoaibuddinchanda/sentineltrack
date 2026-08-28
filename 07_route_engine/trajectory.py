from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timezone
from .models import (
    RouteSighting,
    RouteSegment,
    TargetTrajectory,
    TrajectoryStatus,
    FeasibilityClass,
    TimeQuality,
    LocationQuality,
    CameraGeo
)
from .config import RouteEngineConfig
from .feasibility import evaluate_segment_feasibility


def collapse_same_camera_dwell_sightings(
    sightings: List[RouteSighting]
) -> List[RouteSighting]:
    """
    Collapses consecutive sightings from the same camera into a single node
    preserving dwell duration, best match score, and aggregated support.
    """
    if len(sightings) <= 1:
        return sightings

    collapsed = []
    current = sightings[0]

    for nxt in sightings[1:]:
        if (nxt.camera_id == current.camera_id and 
            nxt.stream_epoch == current.stream_epoch and
            abs((nxt.event_time_utc - current.event_time_utc).total_seconds()) < 120.0):
            # Same camera dwell: merge
            current.last_pts_ms = max(current.last_pts_ms, nxt.last_pts_ms)
            current.match_score = max(current.match_score, nxt.match_score)
            current.support_count += nxt.support_count
            current.ocr_confidence = max(current.ocr_confidence, nxt.ocr_confidence)
        else:
            collapsed.append(current)
            current = nxt

    collapsed.append(current)
    return collapsed


def compute_node_score(sighting: RouteSighting) -> float:
    """Computes evidence score for an individual sighting node."""
    score = sighting.match_score * 0.70 + sighting.ocr_confidence * 0.15

    # Multi-frame support bonus
    if sighting.support_count >= 3:
        score += 0.15
    elif sighting.support_count >= 2:
        score += 0.10

    # Timing quality modifier
    if sighting.time_quality == TimeQuality.LOW:
        score *= 0.85

    # Location quality modifier
    if sighting.location_quality == LocationQuality.UNKNOWN:
        score *= 0.90

    return min(1.0, max(0.0, score))


def solve_best_trajectory_dag(
    candidate_sightings: List[RouteSighting],
    cameras_map: Dict[str, CameraGeo],
    config: Optional[RouteEngineConfig] = None
) -> Tuple[List[RouteSighting], List[RouteSegment], TrajectoryStatus, float, List[List[RouteSighting]], List[str]]:
    """
    Solves the optimal chronological trajectory through candidate sightings using DP.
    Returns (selected_sightings, segments, status, confidence, alternative_paths, warnings).
    """
    cfg = config or RouteEngineConfig.from_yaml()
    warnings: List[str] = []

    if not candidate_sightings:
        return [], [], TrajectoryStatus.NO_ROUTE, 0.0, [], ["No candidate sightings found for target registration."]

    # Sort strictly by event_time_utc (Never by stream-local PTS)
    sorted_sightings = sorted(candidate_sightings, key=lambda s: s.event_time_utc)

    if cfg.collapse_same_camera_dwell:
        sorted_sightings = collapse_same_camera_dwell_sightings(sorted_sightings)

    n = len(sorted_sightings)
    if n == 1:
        s = sorted_sightings[0]
        conf = compute_node_score(s)
        return [s], [], TrajectoryStatus.SINGLE_SIGHTING, round(conf, 4), [], ["Single observation: insufficient evidence to construct route geometry."]

    # Build DAG: For each node i, find valid feasible forward transitions to node j
    # dp[i] = (best_score_ending_at_i, best_parent_index)
    dp_scores = [compute_node_score(s) for s in sorted_sightings]
    parent_ptrs = [-1] * n
    segment_cache: Dict[Tuple[int, int], RouteSegment] = {}

    for j in range(1, n):
        to_s = sorted_sightings[j]
        to_cam = cameras_map.get(to_s.camera_id)
        best_prev_score = -1.0
        best_prev_idx = -1

        lookback_count = 0
        for i in range(j - 1, -1, -1):
            from_s = sorted_sightings[i]
            delta_t = (to_s.event_time_utc - from_s.event_time_utc).total_seconds()
            if delta_t > (cfg.large_gap_seconds * 4) and lookback_count >= 10:
                break

            from_cam = cameras_map.get(from_s.camera_id)
            seg = evaluate_segment_feasibility(from_s, to_s, from_cam, to_cam, config=cfg)
            segment_cache[(i, j)] = seg

            # Skip impossible edges in primary DP path
            if seg.feasibility == FeasibilityClass.IMPOSSIBLE:
                lookback_count += 1
                continue

            trans_score = dp_scores[i] + (seg.segment_score * 0.50) + compute_node_score(to_s)
            if trans_score > best_prev_score:
                best_prev_score = trans_score
                best_prev_idx = i

            lookback_count += 1
            if lookback_count >= 50:
                break

        if best_prev_idx != -1:
            dp_scores[j] = best_prev_score
            parent_ptrs[j] = best_prev_idx

    # Find the end node with highest score
    best_end_idx = int(np.argmax(dp_scores)) if 'np' in globals() else max(range(n), key=lambda idx: dp_scores[idx])

    # Reconstruct best path
    path_indices = []
    curr = best_end_idx
    while curr != -1:
        path_indices.append(curr)
        curr = parent_ptrs[curr]
    path_indices.reverse()

    selected_sightings = [sorted_sightings[idx] for idx in path_indices]

    # Build selected segments
    selected_segments = []
    for idx in range(len(selected_sightings) - 1):
        s_from = selected_sightings[idx]
        s_to = selected_sightings[idx + 1]
        from_cam = cameras_map.get(s_from.camera_id)
        to_cam = cameras_map.get(s_to.camera_id)
        seg = evaluate_segment_feasibility(s_from, s_to, from_cam, to_cam, config=cfg)
        seg.sequence_index = idx + 1
        selected_segments.append(seg)
        warnings.extend(seg.warnings)

    # Check for impossible transitions / conflicts
    has_impossible = any(seg.feasibility == FeasibilityClass.IMPOSSIBLE for seg in selected_segments)
    has_high_conf_conflict = any(
        seg.feasibility == FeasibilityClass.IMPOSSIBLE and 
        s_from.match_score >= 0.85 and s_to.match_score >= 0.85
        for seg, s_from, s_to in zip(selected_segments, selected_sightings[:-1], selected_sightings[1:])
    )

    # Determine Status
    if has_high_conf_conflict:
        status = TrajectoryStatus.CONFLICTING_SIGHTINGS
        warnings.append("High-confidence target observations exist at physically incompatible locations/times.")
    elif len(selected_sightings) >= 2:
        mean_match = sum(s.match_score for s in selected_sightings) / len(selected_sightings)
        if mean_match >= 0.85 and not has_impossible:
            status = TrajectoryStatus.CONFIRMED_SEQUENCE
        else:
            status = TrajectoryStatus.PLAUSIBLE_SEQUENCE
    else:
        status = TrajectoryStatus.INSUFFICIENT_EVIDENCE

    # Trajectory confidence calculation
    avg_node_conf = sum(compute_node_score(s) for s in selected_sightings) / max(len(selected_sightings), 1)
    avg_edge_conf = (sum(seg.segment_score for seg in selected_segments) / max(len(selected_segments), 1)) if selected_segments else 1.0
    trajectory_confidence = round(avg_node_conf * 0.60 + avg_edge_conf * 0.40, 4)

    return selected_sightings, selected_segments, status, trajectory_confidence, [], list(set(warnings))
