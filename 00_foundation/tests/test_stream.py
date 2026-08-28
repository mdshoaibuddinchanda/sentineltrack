import sys
from pathlib import Path

# Ensure 00_foundation and root are on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json
import numpy as np
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

