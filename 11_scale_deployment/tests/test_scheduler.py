import time
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import importlib
FairStreamScheduler = importlib.import_module("11_scale_deployment.scheduler").FairStreamScheduler
ScaleDeploymentConfig = importlib.import_module("11_scale_deployment.config").ScaleDeploymentConfig
FramePacket = importlib.import_module("00_foundation.streams.models").FramePacket


class TestFairStreamScheduler:
    def test_fair_turn_taking_across_cameras(self):
        """Validates that Deficit Round-Robin services all cameras fairly without starvation."""
        cfg = ScaleDeploymentConfig(queue_max_size=10, micro_batch_size=3, max_batch_wait_ms=5.0)
        scheduler = FairStreamScheduler(config=cfg)

        # Register 3 cameras and enqueue 5 frames each
        for cam_idx in range(3):
            cid = f"cam_{cam_idx}"
            scheduler.register_camera(cid)
            for f_idx in range(5):
                pkt = FramePacket(
                    camera_id=cid,
                    pts_ms=float(f_idx * 100),
                    frame=np.zeros((10, 10, 3), dtype=np.uint8),
                    ingest_time_utc=datetime.now(timezone.utc)
                )
                scheduler.enqueue_frame(pkt)

        # First micro-batch should contain 1 frame from each camera (cam_0, cam_1, cam_2)
        batch1 = scheduler.fetch_batch(max_batch_size=3)
        assert len(batch1) == 3
        cams_in_batch1 = {p.camera_id for p in batch1}
        assert cams_in_batch1 == {"cam_0", "cam_1", "cam_2"}

        # Second micro-batch should also contain 1 from each
        batch2 = scheduler.fetch_batch(max_batch_size=3)
        assert len(batch2) == 3
        cams_in_batch2 = {p.camera_id for p in batch2}
        assert cams_in_batch2 == {"cam_0", "cam_1", "cam_2"}

    def test_stale_frame_drop_enforcement(self):
        """Validates that frames older than max_staleness_ms are dropped."""
        cfg = ScaleDeploymentConfig(queue_max_size=10, max_staleness_ms=500.0)
        scheduler = FairStreamScheduler(config=cfg)

        cid = "cam_stale_test"
        scheduler.register_camera(cid)

        # 1. Enqueue a stale frame (2.0 seconds in the past)
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=2.0)
        stale_pkt = FramePacket(
            camera_id=cid,
            pts_ms=100.0,
            frame=np.zeros((10, 10, 3), dtype=np.uint8),
            ingest_time_utc=stale_time
        )
        scheduler.enqueue_frame(stale_pkt)

        # 2. Enqueue a fresh frame (now)
        fresh_pkt = FramePacket(
            camera_id=cid,
            pts_ms=200.0,
            frame=np.zeros((10, 10, 3), dtype=np.uint8),
            ingest_time_utc=datetime.now(timezone.utc)
        )
        scheduler.enqueue_frame(fresh_pkt)

        # Batch fetch should discard the stale frame and return only the fresh frame
        batch = scheduler.fetch_batch(max_batch_size=2)
        assert len(batch) == 1
        assert batch[0].pts_ms == 200.0

        metrics = scheduler.get_metrics()
        assert metrics["total_dropped_stale"] == 1
        assert metrics["total_processed"] == 1

    def test_camera_unregistration_cleans_resources(self):
        scheduler = FairStreamScheduler()
        scheduler.register_camera("cam_temp")
        assert "cam_temp" in scheduler._camera_queues

        scheduler.unregister_camera("cam_temp")
        assert "cam_temp" not in scheduler._camera_queues
        assert "cam_temp" not in scheduler._camera_order
