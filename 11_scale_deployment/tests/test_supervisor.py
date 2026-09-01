import time
import pytest
import threading
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import importlib
supervisor_m = importlib.import_module("11_scale_deployment.supervisor")
FramePacket = importlib.import_module("00_foundation.streams.models").FramePacket
StreamSupervisor = supervisor_m.StreamSupervisor
CameraStreamWorker = supervisor_m.CameraStreamWorker
ScaleDeploymentConfig = importlib.import_module("11_scale_deployment.config").ScaleDeploymentConfig


class TestStreamSupervisor:
    def test_supervisor_dispatches_standardized_reader_packets(self, monkeypatch):
        """A registered camera must forward RTSPReader packets to analytics."""
        delivered = []
        delivered_event = threading.Event()

        class FakeReader:
            def __init__(self, **kwargs):
                self.stream_epoch = 0
                self.released = False

            def connect(self):
                return True

            def packets(self):
                yield FramePacket(
                    camera_id="cam_packet_01",
                    pts_ms=100.0,
                    frame=np.zeros((8, 8, 3), dtype=np.uint8),
                    stream_epoch=1,
                    ingest_time_utc=datetime.now(timezone.utc),
                    event_time_utc=datetime.now(timezone.utc),
                )

            def release(self):
                self.released = True

        monkeypatch.setattr(supervisor_m, "RTSPReader", FakeReader)
        supervisor = StreamSupervisor(
            on_frame_callback=lambda packet: (delivered.append(packet), delivered_event.set())
        )
        supervisor.add_camera("cam_packet_01", "rtsp://dummy/packet")
        supervisor.start()

        assert delivered_event.wait(timeout=1.0)
        supervisor.stop()

        assert len(delivered) == 1
        assert delivered[0].camera_id == "cam_packet_01"

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

    def test_supervisor_marks_connected_worker_stale_without_recent_frames(self):
        worker = CameraStreamWorker(
            camera_id="cam_stale_01",
            rtsp_url="rtsp://dummy",
            stale_after_s=5.0,
        )
        worker.is_connected = True
        worker.last_frame_time = time.time() - 10.0

        supervisor = StreamSupervisor()
        supervisor._workers[worker.camera_id] = worker
        status = supervisor.get_status()

        assert status["connected_cameras"] == 0
        assert status["degraded_cameras"] == 1
        assert status["cameras"][worker.camera_id]["connected"] is False
        assert status["cameras"][worker.camera_id]["degraded"] is True

    def test_supervisor_live_snapshot_requires_fresh_connected_frame(self):
        worker = CameraStreamWorker(
            camera_id="cam_live_01",
            rtsp_url="rtsp://dummy",
            stale_after_s=5.0,
        )
        worker.is_connected = True
        worker.last_frame_time = time.time()
        worker._latest_frame = np.zeros((8, 8, 3), dtype=np.uint8)

        supervisor = StreamSupervisor()
        supervisor._workers[worker.camera_id] = worker

        snapshot = supervisor.get_live_snapshot(worker.camera_id)
        assert snapshot is not None
        frame, frame_time = snapshot
        assert frame.shape == (8, 8, 3)
        assert frame_time > 0

        worker.last_frame_time = time.time() - 10.0
        assert supervisor.get_live_snapshot(worker.camera_id) is None

    def test_dispatch_uses_callback_or_scheduler_exactly_once(self):
        class Scheduler:
            def __init__(self):
                self.received = []

            def enqueue_frame(self, packet):
                self.received.append(packet)

        scheduler = Scheduler()
        callback_packets = []
        supervisor = StreamSupervisor(
            scheduler=scheduler,
            on_frame_callback=callback_packets.append,
        )
        packet = FramePacket(
            camera_id="cam_once",
            pts_ms=1.0,
            frame=np.zeros((4, 4, 3), dtype=np.uint8),
            stream_epoch=1,
        )

        supervisor._dispatch_frame(packet)

        assert callback_packets == [packet]
        assert scheduler.received == []

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
