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

    # Maintain top distinct paths reaching each node: node_paths[j] = [(score, [indices])]
    node_paths: Dict[int, List[Tuple[float, List[int]]]] = {}
    node_paths[0] = [(compute_node_score(sorted_sightings[0]), [0])]

    for j in range(1, n):
        to_s = sorted_sightings[j]
        to_cam = cameras_map.get(to_s.camera_id)
        node_sc = compute_node_score(to_s)
        
        # Single-node path starting at j
        candidates: List[Tuple[float, List[int]]] = [(node_sc, [j])]

        lookback_count = 0
        for i in range(j - 1, -1, -1):
            from_s = sorted_sightings[i]
            delta_t = (to_s.event_time_utc - from_s.event_time_utc).total_seconds()
            if delta_t > (cfg.large_gap_seconds * 4) and lookback_count >= 10:
                break

            from_cam = cameras_map.get(from_s.camera_id)
            seg = evaluate_segment_feasibility(from_s, to_s, from_cam, to_cam, config=cfg)

            # Skip impossible edges
            if seg.feasibility == FeasibilityClass.IMPOSSIBLE:
                lookback_count += 1
                continue

            # Extend paths from node i
            for prev_sc, prev_path in node_paths.get(i, []):
                trans_score = prev_sc + (seg.segment_score * 0.50) + node_sc
                candidates.append((trans_score, prev_path + [j]))

            lookback_count += 1
            if lookback_count >= 50:
                break

        # Deduplicate paths reaching node j by camera sequence and keep top 3
        candidates.sort(key=lambda x: x[0], reverse=True)
        deduped: List[Tuple[float, List[int]]] = []
        seen_cams = set()
        for sc, p in candidates:
            cam_seq = tuple(sorted_sightings[idx].camera_id for idx in p)
            if cam_seq not in seen_cams:
                seen_cams.add(cam_seq)
                deduped.append((sc, p))
            if len(deduped) >= 3:
                break
        node_paths[j] = deduped

    # Collect all terminating candidate paths across all nodes
    all_terminal_paths: List[Tuple[float, List[int]]] = []
    for paths in node_paths.values():
        all_terminal_paths.extend(paths)

    all_terminal_paths.sort(key=lambda x: x[0], reverse=True)

    if not all_terminal_paths:
        return [], [], TrajectoryStatus.NO_ROUTE, 0.0, [], ["No valid trajectory path found."]

    best_score, best_path_indices = all_terminal_paths[0]
    selected_sightings = [sorted_sightings[idx] for idx in best_path_indices]

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

    # 1. Search for Alternative Paths & Ambiguity
    alternative_trajectories: List[List[RouteSighting]] = []
    is_ambiguous = False
    best_cam_seq = tuple(s.camera_id for s in selected_sightings)
    best_set = set(best_path_indices)

    for alt_sc, alt_indices in all_terminal_paths[1:]:
        alt_set = set(alt_indices)
        if alt_set.issubset(best_set) or best_set.issubset(alt_set):
            continue

        alt_sightings = [sorted_sightings[idx] for idx in alt_indices]
        alt_cam_seq = tuple(s.camera_id for s in alt_sightings)

        if alt_cam_seq != best_cam_seq and len(alt_indices) >= 2:
            sel_distinct_scores = [sorted_sightings[idx].match_score for idx in best_path_indices if idx not in alt_set]
            alt_distinct_scores = [sorted_sightings[idx].match_score for idx in alt_indices if idx not in best_set]

            if not alt_distinct_scores or not sel_distinct_scores:
                continue

            mean_sel = sum(sel_distinct_scores) / len(sel_distinct_scores)
            mean_alt = sum(alt_distinct_scores) / len(alt_distinct_scores)

            distinct_diff = mean_sel - mean_alt
            if 0.0 <= distinct_diff <= cfg.ambiguity_margin:
                is_ambiguous = True
                alternative_trajectories.append(alt_sightings)
                if len(alternative_trajectories) >= cfg.max_alternative_paths:
                    break

    # 2. Check for High-Confidence Conflicting Sightings vs Competing Branches
    selected_set = set(best_path_indices)
    has_high_conf_conflict = False

    for unsel_idx, unsel_s in enumerate(sorted_sightings):
        if unsel_idx in selected_set or unsel_s.match_score < 0.85:
            continue

        # Check against high-confidence sightings in the selected path
        for sel_s in selected_sightings:
            if sel_s.match_score < 0.85:
                continue

            first_s, second_s = (unsel_s, sel_s) if unsel_s.event_time_utc <= sel_s.event_time_utc else (sel_s, unsel_s)
            cam1 = cameras_map.get(first_s.camera_id)
            cam2 = cameras_map.get(second_s.camera_id)
            conflict_seg = evaluate_segment_feasibility(first_s, second_s, cam1, cam2, config=cfg)

            if conflict_seg.feasibility == FeasibilityClass.IMPOSSIBLE:
                dist_km = conflict_seg.distance_lower_bound_m / 1000.0
                delta_t_min = conflict_seg.delta_seconds / 60.0

                # If the conflicting sighting is part of a valid alternative path with comparable score
                # and within local proximity (< 10 km), treat as branch ambiguity rather than severe wide-area conflict
                is_local_branch_alternative = (
                    is_ambiguous and 
                    dist_km <= 10.0 and 
                    any(unsel_s.sighting_id in [s.sighting_id for s in alt_p] for alt_p in alternative_trajectories)
                )

                if not is_local_branch_alternative:
                    has_high_conf_conflict = True
                    warnings.append(
                        f"High-confidence target observation conflict detected: Sighting '{unsel_s.sighting_id}' at camera '{unsel_s.camera_id}' (match {unsel_s.match_score:.2f}) "
                        f"conflicts physically with sighting '{sel_s.sighting_id}' at camera '{sel_s.camera_id}' (match {sel_s.match_score:.2f}). "
                        f"Required speed ({conflict_seg.minimum_required_speed_kmh:.1f} km/h over {dist_km:.1f} km in {delta_t_min:.1f} min) exceeds physical limit ({cfg.hard_max_speed_kmh} km/h). "
                        f"Possible causes: clock mismatch, false OCR match, duplicate/cloned registration, incorrect camera coordinates."
                    )
                    break

    # 3. Determine Status
    has_impossible = any(seg.feasibility == FeasibilityClass.IMPOSSIBLE for seg in selected_segments)

    if has_high_conf_conflict:
        status = TrajectoryStatus.CONFLICTING_SIGHTINGS
    elif is_ambiguous:
        status = TrajectoryStatus.AMBIGUOUS
        warnings.append(
            f"Trajectory ambiguity: multiple plausible paths with comparable score."
        )
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

    return selected_sightings, selected_segments, status, trajectory_confidence, alternative_trajectories, list(dict.fromkeys(warnings))

