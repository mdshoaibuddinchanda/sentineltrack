import sys
from pathlib import Path

# Ensure 00_foundation and root are on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json
import numpy as np
import cv2
from unittest.mock import patch, MagicMock
from streams.probe import probe_rtsp
from streams.health import StreamHealthTracker
from streams.models import FramePacket
from streams.reader import RTSPReader


def test_probe_rtsp_h264_success():
    fake_ffprobe_output = json.dumps({
        "streams": [
            {
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "30/1",
            }
        ]
    })

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_ffprobe_output, stderr="")
        res = probe_rtsp("rtsp://mock.stream/live")

        assert res["success"] is True
        assert res["codec"] == "h264"
        assert res["width"] == 1920
        assert res["height"] == 1080
        assert res["reported_fps"] == 30.0


def test_probe_rtsp_h265_success():
    fake_ffprobe_output = json.dumps({
        "streams": [
            {
                "codec_name": "hevc",
                "width": 1280,
                "height": 720,
                "avg_frame_rate": "25/1",
            }
        ]
    })

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_ffprobe_output, stderr="")
        res = probe_rtsp("rtsp://mock.stream/live_h265")

        assert res["success"] is True
        assert res["codec"] == "hevc"
        assert res["width"] == 1280
        assert res["height"] == 720
        assert res["reported_fps"] == 25.0


def test_probe_rtsp_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Connection refused")
        res = probe_rtsp("rtsp://invalid.stream/live")

        assert res["success"] is False
        assert "Connection refused" in res["error"]


def test_probe_rtsp_falls_back_to_opencv_when_ffprobe_is_unavailable():
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    capture = MagicMock()
    capture.isOpened.return_value = True
    capture.read.return_value = (True, frame)

    def capture_get(prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return 640.0
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return 360.0
        if prop == cv2.CAP_PROP_FPS:
            return 25.0
        return 0.0

    capture.get.side_effect = capture_get
    with patch("subprocess.run", side_effect=FileNotFoundError), patch(
        "cv2.VideoCapture", return_value=capture
    ):
        res = probe_rtsp("https://mock.stream/live.m3u8", timeout=2)

    assert res["success"] is True
    assert res["probe_backend"] == "opencv"
    assert res["width"] == 640
    assert res["height"] == 360


def test_stream_health_tracker():
    with patch("streams.health.record_health_event") as mock_record, \
         patch("streams.health.update_camera_probe_status") as mock_update:

        tracker = StreamHealthTracker(camera_id="cam_01", expected_fps=25.0)

        # Connection event
        tracker.on_connected(latency_ms=120.5)
        mock_record.assert_called_with(
            camera_id="cam_01",
            event_type="STREAM_CONNECTED",
            message="Connected to stream. First frame latency: 120.50ms",
        )
        mock_update.assert_called_with(
            camera_id="cam_01",
            stream_status="ONLINE",
            first_frame_latency_ms=120.5,
        )

        # Normal frame
        tracker.on_frame(pts_ms=1000.0)
        assert tracker.last_pts_ms == 1000.0

        # Frame drop detection (expected delta is 40ms, delta here is 500ms > 3 * 40ms)
        tracker.on_frame(pts_ms=1500.0)
        assert mock_record.call_args[1]["event_type"] == "FRAME_DROP"

        # Disconnection event
        tracker.on_disconnected(reason="EOF")
        assert mock_record.call_args[1]["event_type"] == "STREAM_DISCONNECTED"


def test_frame_packet_creation():
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    packet = FramePacket(
        camera_id="camera_17",
        pts_ms=182022.41,
        frame=dummy_frame,
        stream_epoch=1,
    )
    assert packet.camera_id == "camera_17"
    assert packet.pts_ms == 182022.41
    assert packet.stream_epoch == 1
    assert packet.frame.shape == (480, 640, 3)


def test_rtsp_reader_epoch_reset():
    reader = RTSPReader(url="rtsp://mock.stream/live", camera_id="cam_loop")

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    # Simulate frame reads: PTS increases, then suddenly resets to 0 (recording loop)
    pts_sequence = [1000.0, 2000.0, 5000.0, 100.0]  # Jump backward from 5000 to 100
    mock_cap.read.side_effect = [(True, np.zeros((10, 10, 3), dtype=np.uint8))] * len(pts_sequence)
    mock_cap.get.side_effect = pts_sequence

    with patch("cv2.VideoCapture", return_value=mock_cap):
        gen = reader.frames()

        f1, pts1 = next(gen)
        assert pts1 == 1000.0
        assert reader.stream_epoch == 0

        f2, pts2 = next(gen)
        assert pts2 == 2000.0
        assert reader.stream_epoch == 0

        f3, pts3 = next(gen)
        assert pts3 == 5000.0
        assert reader.stream_epoch == 0

        f4, pts4 = next(gen)
        assert pts4 == 100.0
        # Epoch should have incremented on loop!
        assert reader.stream_epoch == 1


def test_rtsp_reader_uses_bounded_capture_timeouts():
    reader = RTSPReader(
        url="rtsp://mock.stream/live",
        camera_id="cam_timeout",
        connect_timeout_s=4.5,
    )
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    with patch("cv2.VideoCapture", return_value=mock_cap) as capture:
        assert reader.connect() is True

    assert capture.call_args.args[0] == "rtsp://mock.stream/live"
    assert capture.call_args.args[1] == cv2.CAP_FFMPEG
    assert capture.call_args.args[2] == [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
        4500,
        cv2.CAP_PROP_READ_TIMEOUT_MSEC,
        4500,
    ]


def test_rtsp_reader_runtime_failover_to_hls():
    reader = RTSPReader(
        url="rtsp://mock.stream/live",
        fallback_url="https://mock.stream/live.m3u8",
        camera_id="cam_failover",
        failover_threshold=2
    )

    mock_cap_fail = MagicMock()
    mock_cap_fail.isOpened.return_value = False

    mock_cap_hls = MagicMock()
    mock_cap_hls.isOpened.return_value = True

    # First 2 connect attempts fail on primary RTSP -> Failover to HLS succeeds
    def mock_videocapture_factory(url, *args, **kwargs):
        if "rtsp://" in url:
            return mock_cap_fail
        else:
            return mock_cap_hls

    with patch("cv2.VideoCapture", side_effect=mock_videocapture_factory):
        # Trigger connects to hit failure threshold
        assert reader.connect() is False
        assert reader.is_using_fallback is False

        assert reader.connect() is True
        assert reader.is_using_fallback is True
        assert reader.active_url == "https://mock.stream/live.m3u8"


def test_frame_packet_timing_utc_and_provenance():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    dummy_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    packet = FramePacket(
        camera_id="cam_time",
        pts_ms=5000.0,
        frame=dummy_frame,
        stream_epoch=1,
        ingest_time_utc=now,
        event_time_utc=now,
        event_time_source="PTS_ANCHORED_ESTIMATE",
        event_time_quality="MEDIUM"
    )
    assert packet.ingest_time_utc.tzinfo is not None
    assert packet.event_time_source == "PTS_ANCHORED_ESTIMATE"
    assert packet.event_time_quality == "MEDIUM"


def test_reader_packets_anchored_pts_calculation():
    reader = RTSPReader(url="rtsp://mock.stream/live", camera_id="cam_anchored")
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    pts_sequence = [1000.0, 2000.0, 3000.0]
    mock_cap.read.side_effect = [(True, np.zeros((10, 10, 3), dtype=np.uint8))] * len(pts_sequence)
    mock_cap.get.side_effect = pts_sequence

    with patch("cv2.VideoCapture", return_value=mock_cap):
        gen = reader.packets()
        packets = [next(gen) for _ in range(3)]
        assert len(packets) == 3
        p1, p2, p3 = packets
        assert p1.event_time_source == 'PTS_ANCHORED_ESTIMATE'
        assert p1.event_time_quality == 'MEDIUM'
        # Event time delta must reflect PTS delta (1000ms = 1s)
        delta_1_2 = (p2.event_time_utc - p1.event_time_utc).total_seconds()
        assert abs(delta_1_2 - 1.0) < 0.05


def test_reader_packets_unknown_pts_handling():
    reader = RTSPReader(url="rtsp://mock.stream/live", camera_id="cam_unknown_pts")
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    pts_sequence = [-1.0, -1.0]
    mock_cap.read.side_effect = [(True, np.zeros((10, 10, 3), dtype=np.uint8))] * len(pts_sequence)
    mock_cap.get.side_effect = pts_sequence

    with patch("cv2.VideoCapture", return_value=mock_cap):
        gen = reader.packets()
        packets = [next(gen) for _ in range(2)]
        assert len(packets) == 2
        for p in packets:
            assert p.pts_ms == -1.0
            assert p.event_time_source == 'INGEST_TIME'
            assert p.event_time_quality == 'LOW'


def test_bounded_stream_queue_drop_behavior():
    from streams.bounded_stream_queue import BoundedStreamQueue
    bq = BoundedStreamQueue(maxsize=3)
    for i in range(10):
        bq.put_latest(f"frame_{i}")

    assert bq.qsize() == 3
    metrics = bq.get_metrics()
    assert metrics['total_enqueued'] == 10
    assert metrics['total_dropped'] == 7
    assert metrics['qsize'] == 3
    # Verify latest frames were kept: 7, 8, 9
    assert bq.get() == "frame_7"
    assert bq.get() == "frame_8"
    assert bq.get() == "frame_9"
