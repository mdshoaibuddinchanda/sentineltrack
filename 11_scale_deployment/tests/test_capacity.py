import pytest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import importlib
cap_m = importlib.import_module("11_scale_deployment.capacity")
compute_required_aggregate_fps = cap_m.compute_required_aggregate_fps
compute_max_cameras_for_node = cap_m.compute_max_cameras_for_node
evaluate_capacity = cap_m.evaluate_capacity


class TestCapacityModel:
    def test_required_fps_calculation(self):
        # 50 cameras, base=1.0 FPS, burst=5.0 FPS, burst_ratio=10% (0.10)
        # effective fps per cam = 0.9 * 1.0 + 0.1 * 5.0 = 1.4 FPS
        # 50 * 1.4 = 70.0 FPS
        req_fps = compute_required_aggregate_fps(camera_count=50, base_fps=1.0, burst_fps=5.0, burst_ratio=0.10)
        assert req_fps == pytest.approx(70.0, 0.01)

    def test_max_cameras_single_node(self):
        # Measured node FPS = 45.0, safety margin = 80% (usable = 36.0 FPS)
        # effective fps per cam = 1.4 FPS
        # 36.0 / 1.4 = 25.7 -> 25 cameras
        max_cams = compute_max_cameras_for_node(measured_node_fps=45.0, base_fps=1.0, burst_fps=5.0, burst_ratio=0.10)
        assert max_cams == 25

    def test_evaluate_capacity_classification(self):
        report_50 = evaluate_capacity(camera_count=50, measured_node_fps=75.0)
        assert report_50.classification == "MEASURED"
        assert report_50.sustainable is True

        report_80k = evaluate_capacity(camera_count=80000, measured_node_fps=45.0)
        assert report_80k.classification == "PROJECTED"
        assert report_80k.projected_nodes_for_80k_cams > 0
