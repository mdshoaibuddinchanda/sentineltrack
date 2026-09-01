import time
import numpy as np
import pytest
import importlib
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

analytics_mod = importlib.import_module("08_backend.services.analytics_service")
p0_models = importlib.import_module("00_foundation.streams.models")
p1_models = importlib.import_module("01_vehicle_detection.models")
p5_models = importlib.import_module("05_target_matching.models")
p5_repo = importlib.import_module("05_target_matching.repository")
p5_watch = importlib.import_module("05_target_matching.watchlist")
backend_app = importlib.import_module("08_backend.app")

AnalyticsWorker = analytics_mod.AnalyticsWorker
FramePacket = p0_models.FramePacket
VehicleDetection = p1_models.VehicleDetection
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


def test_analytics_worker_deterministic_positive_path_and_timing_propagation():
    """
    Deterministic positive-path integration test exercising the full chain:
    FramePacket -> P1 Vehicle Detection -> P2 Tracking -> P3 Plate Detection -> P4 OCR (min_support_count=2) -> P5 Target Matching -> Sighting/Alert.
    Asserts that UTC event time and metadata survive into the resulting P5 Sighting and Alert.
    """
    worker = AnalyticsWorker()
    worker._lazy_init_models()

    target_plate = "GJ01MT0999"
    # Seed target into watchlist
    shared_wm = importlib.import_module("08_backend.services.target_service").get_shared_watchlist_manager()
    shared_wm.add_entry(registration=target_plate, priority=p5_models.WatchlistPriority.CRITICAL)

    event_time_1 = datetime(2026, 8, 28, 14, 30, 0, tzinfo=timezone.utc)
    event_time_2 = datetime(2026, 8, 28, 14, 30, 1, tzinfo=timezone.utc)

    dummy_frame_1 = np.ones((720, 1280, 3), dtype=np.uint8) * 100
    dummy_frame_2 = np.ones((720, 1280, 3), dtype=np.uint8) * 105

    packet1 = FramePacket(
        camera_id="cam_det_pos_01",
        pts_ms=1000.0,
        frame=dummy_frame_1,
        stream_epoch=1,
        ingest_time_utc=event_time_1,
        event_time_utc=event_time_1,
        event_time_source="SOURCE_WALLCLOCK",
        event_time_quality="HIGH"
    )

    packet2 = FramePacket(
        camera_id="cam_det_pos_01",
        pts_ms=1033.0,
        frame=dummy_frame_2,
        stream_epoch=1,
        ingest_time_utc=event_time_2,
        event_time_utc=event_time_2,
        event_time_source="PTS_ANCHORED_ESTIMATE",
        event_time_quality="HIGH"
    )

    # Mock P1, P3, and P4 recognizer deterministically
    fake_dets = [
        VehicleDetection(
            camera_id="cam_det_pos_01",
            pts_ms=1000.0,
            stream_epoch=1,
            class_id=2,
            class_name="car",
            confidence=0.95,
            x1=100.0,
            y1=100.0,
            x2=500.0,
            y2=400.0
        )
    ]
    fake_plates = [{"x1": 50.0, "y1": 150.0, "x2": 250.0, "y2": 200.0, "confidence": 0.95}]

    p3_pipe_mod = importlib.import_module("03_plate_detection.pipeline")
    with patch.object(worker._detector, "detect_batch", return_value=[fake_dets]):
        with patch.object(worker._plate_detector, "detect", return_value=fake_plates):
            with patch.object(worker._plate_detector, "detect_batch", return_value=[fake_plates]):
                with patch.object(p3_pipe_mod, "compute_plate_quality", return_value=(200.0, 128.0, 0.92)):
                    with patch.object(worker._ocr_pipeline.recognizer, "recognize", return_value=(target_plate, 0.98, [0.98]*12)):
                        # Frame 1 -> Support count = 1
                        res1 = worker.process_single_frame(packet1)
                        assert res1["status"] == "PROCESSED"

                        # Frame 2 -> Support count = 2 (triggers consensus + P5 sighting)
                        res2 = worker.process_single_frame(packet2)
                        assert res2["status"] == "PROCESSED"

    # Query repository to verify sighting and alert persistence with timing
    repo = p5_repo.PostgresTargetMatchingRepository()
    sightings = repo.query_sightings(registration_pattern=target_plate, min_score=0.80)
    assert len(sightings) >= 1
    s = sightings[0]
    assert s["registration_candidate"] == target_plate
    assert s["match_score"] >= 0.90
    assert "event_time_utc" in s
    assert s["event_time_source"] in ["SOURCE_WALLCLOCK", "PTS_ANCHORED_ESTIMATE"]
    assert s["event_time_quality"] == "HIGH"


def test_analytics_worker_real_model_smoke_test():
    """Real-model smoke test passing a basic frame without exceptions."""
    worker = AnalyticsWorker()
    worker._lazy_init_models()

    event_time = datetime(2026, 8, 28, 14, 30, 0, tzinfo=timezone.utc)
    packet = FramePacket(
        camera_id="cam_smoke_01",
        pts_ms=54321.0,
        frame=np.zeros((720, 1280, 3), dtype=np.uint8),
        stream_epoch=1,
        ingest_time_utc=event_time,
        event_time_utc=event_time,
        event_time_source="PTS_ANCHORED_ESTIMATE",
        event_time_quality="HIGH"
    )

    res = worker.process_single_frame(packet)
    assert res["status"] == "PROCESSED"
    assert res["camera_id"] == "cam_smoke_01"


def test_fastapi_lifespan_starts_and_stops_worker():
    """Verifies that FastAPI lifespan starts the background analytics worker and stops it on exit."""
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        worker = analytics_mod.get_analytics_worker()
        assert worker.is_running()

    # After exiting lifespan context
    assert not worker.is_running()
