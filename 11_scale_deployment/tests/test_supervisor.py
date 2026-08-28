import time
import pytest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import importlib
supervisor_m = importlib.import_module("11_scale_deployment.supervisor")
StreamSupervisor = supervisor_m.StreamSupervisor
CameraStreamWorker = supervisor_m.CameraStreamWorker
ScaleDeploymentConfig = importlib.import_module("11_scale_deployment.config").ScaleDeploymentConfig


class TestStreamSupervisor:
    def test_camera_worker_burst_mode_transition(self):
        worker = CameraStreamWorker(
            camera_id="cam_burst_01",
            rtsp_url="rtsp://dummy",
            base_fps=1.0,
            burst_fps=5.0,
            burst_duration_s=0.2
        )

        assert worker.is_in_burst() is False
        assert worker.get_current_target_fps() == 1.0

        # Trigger burst
        worker.trigger_burst(duration_s=0.2)
        assert worker.is_in_burst() is True
        assert worker.get_current_target_fps() == 5.0

        # Wait for burst duration to expire
        time.sleep(0.25)
        assert worker.is_in_burst() is False
        assert worker.get_current_target_fps() == 1.0

    def test_supervisor_shard_filtering(self):
        # Supervisor configured for shard 0 out of 2 shards
        cfg = ScaleDeploymentConfig(shard_count=2, shard_index=0)
        supervisor = StreamSupervisor(config=cfg)

        cam_0_accepted = supervisor.add_camera("camera_000", "rtsp://dummy/0")
        status = supervisor.get_status()
        assert status["shard_index"] == 0
        assert status["shard_count"] == 2

    def test_supervisor_lifecycle_and_cleanup(self):
        supervisor = StreamSupervisor()
        supervisor.add_camera("cam_temp_01", "rtsp://dummy/1")
        assert "cam_temp_01" in supervisor._workers

        supervisor.remove_camera("cam_temp_01")
        assert "cam_temp_01" not in supervisor._workers
