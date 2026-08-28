import pytest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import importlib
shard_m = importlib.import_module("11_scale_deployment.shard")
get_camera_shard = shard_m.get_camera_shard
is_camera_assigned_to_shard = shard_m.is_camera_assigned_to_shard
filter_cameras_for_shard = shard_m.filter_cameras_for_shard
get_shard_distribution = shard_m.get_shard_distribution


class TestSharding:
    def test_single_shard_assigns_all_cameras_to_shard_zero(self):
        cameras = [f"camera_{i:03d}" for i in range(50)]
        for cid in cameras:
            assert get_camera_shard(cid, shard_count=1) == 0
            assert is_camera_assigned_to_shard(cid, shard_index=0, shard_count=1) is True
            assert is_camera_assigned_to_shard(cid, shard_index=1, shard_count=1) is False

    def test_deterministic_shard_assignment(self):
        """Validates that a camera always maps to the exact same shard across calls."""
        cid = "bl_01_entrance_gate"
        shard_count = 4
        shard_a = get_camera_shard(cid, shard_count)
        shard_b = get_camera_shard(cid, shard_count)
        assert shard_a == shard_b
        assert 0 <= shard_a < shard_count

    def test_complete_partitioning_invariant(self):
        """Every camera belongs to exactly one shard; total partitioned count equals total cameras."""
        cameras = [f"camera_{i:04d}" for i in range(100)]
        shard_count = 4

        distribution = get_shard_distribution(cameras, shard_count)
        all_assigned = []
        for shard_idx in range(shard_count):
            cams_in_shard = distribution[shard_idx]
            all_assigned.extend(cams_in_shard)
            filtered = filter_cameras_for_shard(cameras, shard_idx, shard_count)
            assert cams_in_shard == filtered

        # No camera is lost or duplicated
        assert len(all_assigned) == 100
        assert set(all_assigned) == set(cameras)
