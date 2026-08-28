import numpy as np
import pytest
import importlib
from datetime import datetime, timezone

analytics_mod = importlib.import_module("08_backend.services.analytics_service")
p0_models = importlib.import_module("00_foundation.streams.models")

AnalyticsWorker = analytics_mod.AnalyticsWorker
FramePacket = p0_models.FramePacket


def test_analytics_worker_enqueue_and_queue_metrics():
    worker = AnalyticsWorker()
    cam_id = "test_worker_cam_01"

    packet = FramePacket(
        camera_id=cam_id,
        pts_ms=1000.0,
        frame=np.zeros((100, 100, 3), dtype=np.uint8),
        stream_epoch=1,
        ingest_time_utc=datetime.now(timezone.utc),
        event_time_utc=datetime.now(timezone.utc),
        event_time_source="SOURCE_WALLCLOCK",
        event_time_quality="HIGH"
    )

    # Enqueue frame
    ok = worker.enqueue_frame(packet)
    assert ok is True

    status = worker.get_status()
    assert cam_id in status["queues"]
    assert status["queues"][cam_id]["qsize"] >= 1
    assert status["active_camera_count"] >= 1


def test_analytics_worker_process_single_frame():
    worker = AnalyticsWorker()
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    packet = FramePacket(
        camera_id="test_worker_cam_02",
        pts_ms=2000.0,
        frame=dummy_frame,
        stream_epoch=1,
        ingest_time_utc=datetime.now(timezone.utc),
        event_time_utc=datetime.now(timezone.utc),
        event_time_source="PTS_ANCHORED_ESTIMATE",
        event_time_quality="MEDIUM"
    )

    result = worker.process_single_frame(packet)
    assert result["camera_id"] == "test_worker_cam_02"
    assert "detections" in result
    assert "tracks" in result
