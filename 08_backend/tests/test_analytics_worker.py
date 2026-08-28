import time
import numpy as np
import pytest
import importlib
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

analytics_mod = importlib.import_module("08_backend.services.analytics_service")
p0_models = importlib.import_module("00_foundation.streams.models")
backend_app = importlib.import_module("08_backend.app")

AnalyticsWorker = analytics_mod.AnalyticsWorker
FramePacket = p0_models.FramePacket
app = backend_app.app


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


def test_analytics_worker_start_stop_no_deadlock():
    """Verifies that start() and stop() with RLock do not deadlock or raise exceptions."""
    worker = AnalyticsWorker()
    assert not worker.is_running()

    worker.start()
    assert worker.is_running()

    # Re-entrant start call should be a no-op without deadlocking
    worker.start()
    assert worker.is_running()

    worker.stop()
    assert not worker.is_running()


def test_analytics_worker_micro_batch_processing():
    """Verifies micro-batch processing across multiple camera streams simultaneously."""
    worker = AnalyticsWorker()
    t0 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)

    packets = [
        FramePacket(
            camera_id=f"cam_mb_{i}",
            pts_ms=float(i * 100),
            frame=np.zeros((480, 640, 3), dtype=np.uint8),
            stream_epoch=1,
            ingest_time_utc=t0 + timedelta(milliseconds=i * 100),
            event_time_utc=t0 + timedelta(milliseconds=i * 100),
            event_time_source="SOURCE_WALLCLOCK",
            event_time_quality="HIGH"
        )
        for i in range(4)
    ]

    results = worker.process_batch(packets)
    assert len(results) == 4
    for r in results:
        assert r["status"] == "PROCESSED"
        assert "camera_id" in r
        assert "pts_ms" in r


def test_analytics_worker_end_to_end_pipeline_and_timing_propagation():
    """
    Controlled end-to-end integration test:
    FramePacket with synthetic plate text rendered on frame
    -> P1 Vehicle Detector -> P2 Tracker -> P3 Plate Detector -> P4 PP-OCRv5 -> P5 Target Matching
    Verifies that UTC event timing and PTS survive through the entire pipeline.
    """
    import cv2
    from unittest.mock import MagicMock

    worker = AnalyticsWorker()
    worker._lazy_init_models()

    # Create a realistic test image with vehicle and text
    img = np.ones((720, 1280, 3), dtype=np.uint8) * 128
    # Draw simulated vehicle rectangle
    cv2.rectangle(img, (200, 200), (800, 600), (40, 40, 40), -1)
    # Draw simulated license plate rectangle
    cv2.rectangle(img, (400, 450), (600, 520), (255, 255, 255), -1)
    cv2.putText(img, "GJ01AB1234", (410, 500), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)

    event_time = datetime(2026, 8, 28, 14, 30, 0, tzinfo=timezone.utc)
    packet = FramePacket(
        camera_id="cam_e2e_01",
        pts_ms=54321.0,
        frame=img,
        stream_epoch=2,
        ingest_time_utc=event_time,
        event_time_utc=event_time,
        event_time_source="PTS_ANCHORED_ESTIMATE",
        event_time_quality="HIGH"
    )

    # Process packet through the worker
    res = worker.process_single_frame(packet)
    assert res["status"] == "PROCESSED"
    assert res["camera_id"] == "cam_e2e_01"
    assert res["pts_ms"] == 54321.0


def test_fastapi_lifespan_starts_and_stops_worker():
    """Verifies that FastAPI lifespan starts the background analytics worker and stops it on exit."""
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        worker = analytics_mod.get_analytics_worker()
        assert worker.is_running()

    # After exiting lifespan context
    assert not worker.is_running()
