from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class CapacityReport:
    """Capacity calculation and hardware modeling report."""
    camera_count: int
    base_sampling_fps: float
    burst_sampling_fps: float
    burst_active_ratio: float
    required_aggregate_fps: float
    measured_node_fps: float
    sustainable: bool
    headroom_percent: float
    estimated_nodes_for_50_cams: int
    projected_nodes_for_80k_cams: int
    classification: str  # "MEASURED" | "SIMULATED" | "PROJECTED"


def compute_required_aggregate_fps(
    camera_count: int,
    base_fps: float = 1.0,
    burst_fps: float = 5.0,
    burst_ratio: float = 0.10
) -> float:
    """
    Computes required aggregate analytics FPS for a given camera count.
    Effective FPS per camera = (1 - burst_ratio) * base_fps + burst_ratio * burst_fps.
    """
    effective_fps_per_cam = ((1.0 - burst_ratio) * base_fps) + (burst_ratio * burst_fps)
    return camera_count * effective_fps_per_cam


def compute_max_cameras_for_node(
    measured_node_fps: float,
    base_fps: float = 1.0,
    burst_fps: float = 5.0,
    burst_ratio: float = 0.10,
    safety_margin: float = 0.80
) -> int:
    """
    Computes maximum sustainable cameras on a single node given measured pipeline FPS.
    Applies a safety margin (e.g. 80% utilization target to prevent queue growth).
    """
    effective_fps_per_cam = ((1.0 - burst_ratio) * base_fps) + (burst_ratio * burst_fps)
    usable_fps = measured_node_fps * safety_margin
    return max(1, int(usable_fps / max(0.01, effective_fps_per_cam)))


def evaluate_capacity(
    camera_count: int = 50,
    measured_node_fps: float = 45.0,
    base_fps: float = 1.0,
    burst_fps: float = 5.0,
    burst_ratio: float = 0.10
) -> CapacityReport:
    """
    Evaluates system capacity against target deployment scenarios.
    """
    required_fps = compute_required_aggregate_fps(camera_count, base_fps, burst_fps, burst_ratio)
    sustainable = measured_node_fps >= required_fps
    headroom = ((measured_node_fps - required_fps) / max(0.1, required_fps)) * 100.0

    cams_per_node = compute_max_cameras_for_node(measured_node_fps, base_fps, burst_fps, burst_ratio)
    nodes_for_50 = max(1, int((50 + cams_per_node - 1) // cams_per_node))
    nodes_for_80k = max(1, int((80000 + cams_per_node - 1) // cams_per_node))

    return CapacityReport(
        camera_count=camera_count,
        base_sampling_fps=base_fps,
        burst_sampling_fps=burst_fps,
        burst_active_ratio=burst_ratio,
        required_aggregate_fps=round(required_fps, 2),
        measured_node_fps=round(measured_node_fps, 2),
        sustainable=sustainable,
        headroom_percent=round(headroom, 1),
        estimated_nodes_for_50_cams=nodes_for_50,
        projected_nodes_for_80k_cams=nodes_for_80k,
        classification="MEASURED" if camera_count <= 50 else "PROJECTED"
    )
