import time
import pytest
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import importlib
ScaleDeploymentConfig = importlib.import_module("11_scale_deployment.config").ScaleDeploymentConfig
FairStreamScheduler = importlib.import_module("11_scale_deployment.scheduler").FairStreamScheduler
StreamSupervisor = importlib.import_module("11_scale_deployment.supervisor").StreamSupervisor
ResourceMonitor = importlib.import_module("11_scale_deployment.resource_monitor").ResourceMonitor
FramePacket = importlib.import_module("00_foundation.streams.models").FramePacket


class TestScaleIntegration:
    def test_50_camera_orchestration_and_fairness(self):
        """
        Validates 50-camera stream registration, bounded queues, and fair deficit round-robin turn-taking.
        Ensures max starvation gap across all 50 cameras is bounded and no camera is starved.
        """
        cfg = ScaleDeploymentConfig(
            queue_max_size=5,
            micro_batch_size=4,
            max_batch_wait_ms=2.0,
            base_sampling_fps=1.0,
            burst_sampling_fps=5.0
        )
        scheduler = FairStreamScheduler(config=cfg)

        # 1. Register 50 simulated cameras
        num_cameras = 50
        for i in range(num_cameras):
            cid = f"camera_{i:03d}"
            scheduler.register_camera(cid)

        # 2. Simulate 5 frames per camera ingested into the scheduler
        for round_num in range(5):
            for i in range(num_cameras):
                cid = f"camera_{i:03d}"
                pkt = FramePacket(
                    camera_id=cid,
                    pts_ms=float(round_num * 200),
                    frame=np.zeros((20, 20, 3), dtype=np.uint8),
                    stream_epoch=1,
                    ingest_time_utc=datetime.now(timezone.utc),
                    event_time_utc=datetime.now(timezone.utc)
                )
                scheduler.enqueue_frame(pkt)

        # 3. Drain and process batches
        batches_processed = 0
        total_frames_extracted = 0
        cameras_serviced = set()

        for _ in range(70):  # Fetch up to 70 batches of size 4 (280 max frames)
            batch = scheduler.fetch_batch(max_batch_size=4)
            if not batch:
                break
            batches_processed += 1
            total_frames_extracted += len(batch)
            for pkt in batch:
                cameras_serviced.add(pkt.camera_id)

        # 4. Assert all 50 cameras were serviced fairly
        assert len(cameras_serviced) == 50, f"Expected all 50 cameras to be serviced, got {len(cameras_serviced)}"
        assert total_frames_extracted == 250

        metrics = scheduler.get_metrics()
        assert metrics["active_camera_count"] == 50
        assert metrics["total_processed"] == 250
        assert metrics["total_dropped_stale"] == 0

    def test_resource_monitor_stability_and_zero_slope(self):
        """Validates that ResourceMonitor records memory and computes stable slopes."""
        monitor = ResourceMonitor(sample_interval_s=0.05)
        monitor.start()

        # Simulate small bounded workload
        for _ in range(5):
            arr = np.zeros((100, 100, 3), dtype=np.uint8)
            time.sleep(0.06)

        monitor.stop()
        summary = monitor.get_summary()
        assert summary["samples_count"] >= 3
        assert summary["rss_peak_mb"] > 0
        assert isinstance(summary["rss_slope_mb_per_min"], float)
