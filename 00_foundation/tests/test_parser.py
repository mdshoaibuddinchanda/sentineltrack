import sys
from pathlib import Path

# Ensure 00_foundation and root are on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from catalogue.models import CameraRecord
from catalogue.parser import parse_camera, parse_catalogue, first_value



def test_first_value_helper():
    data = {"a": None, "b": "val_b", "c": "val_c"}
    assert first_value(data, "a", "b", "c") == "val_b"
    assert first_value(data, "nonexistent", "missing") is None


def test_parse_camera_flat_format():
    raw = {
        "camera_id": "cam_01",
        "name": "North Gate",
        "department": "Security",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "codec": "h264",
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "bitrate": 4000000,
        "live": True,
        "rtsp_url": "rtsp://10.0.0.1/live",
    }
    rec = parse_camera(raw)
    assert isinstance(rec, CameraRecord)
    assert rec.camera_id == "cam_01"
    assert rec.name == "North Gate"
    assert rec.latitude == 37.7749
    assert rec.longitude == -122.4194
    assert rec.codec == "h264"
    assert rec.width == 1920
    assert rec.height == 1080
    assert rec.reported_fps == 30.0
    assert rec.live is True
    assert rec.rtsp_url == "rtsp://10.0.0.1/live"


def test_parse_camera_nested_format():
    raw = {
        "id": "cam_nested",
        "label": "West Exit",
        "location": {"lat": 40.7128, "lng": -74.0060},
        "stream": {
            "rtsp": "rtsp://stream.local/west",
            "webrtc": "https://webrtc.local/west",
            "hls": "https://hls.local/west.m3u8",
        },
        "video_codec": "hevc",
        "is_active": True,
    }
    rec = parse_camera(raw)
    assert rec.camera_id == "cam_nested"
    assert rec.name == "West Exit"
    assert rec.latitude == 40.7128
    assert rec.longitude == -74.0060
    assert rec.rtsp_url == "rtsp://stream.local/west"
    assert rec.webrtc_url == "https://webrtc.local/west"
    assert rec.hls_url == "https://hls.local/west.m3u8"
    assert rec.codec == "hevc"


def test_parse_catalogue_dict_and_list():
    items = [
        {"id": "1", "rtsp": "rtsp://cam1"},
        {"id": "2", "rtsp": "rtsp://cam2"},
    ]
    # As list
    res_list = parse_catalogue(items)
    assert len(res_list) == 2
    assert res_list[0].camera_id == "1"

    # As dict with 'cameras' key
    res_dict = parse_catalogue({"cameras": items})
    assert len(res_dict) == 2

    # As dict with 'data' key
    res_data = parse_catalogue({"data": items})
    assert len(res_data) == 2


def test_parse_camera_missing_id_raises():
    with pytest.raises(ValueError):
        parse_camera({"name": "No ID Cam"})


def test_parse_organizer_location_label_and_effective_hls_host():
    rec = parse_camera(
        {
            "id": "1",
            "name": "Camera 1",
            "location": "01 Chiman bhai Bridge",
            "hls_live_url": "/live/stream/1/index.m3u8",
        },
        base_host="https://cctv.corp8.cloud",
    )

    assert rec.name == "01 Chiman bhai Bridge"
    assert rec.hls_url == "https://cctv.corp8.cloud/live/stream/1/index.m3u8"


def test_parse_current_portal_registry_derives_authenticated_hls_playlist():
    rec = parse_camera(
        {"id": "cam01", "name": "01 Chiman bhai Bridge"},
        base_host="https://cctv.corp8.cloud",
    )

    assert rec.camera_id == "cam01"
    assert rec.name == "01 Chiman bhai Bridge"
    assert rec.hls_url == "https://cctv.corp8.cloud/cam01/index.m3u8"
    assert rec.rtsp_url == "rtsp://103.250.160.189:8554/stream/cam01"
    assert rec.webrtc_url == "http://103.250.160.189:8889/stream/cam01/whep"
