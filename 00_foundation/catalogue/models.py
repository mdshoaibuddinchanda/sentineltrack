from typing import Any
from pydantic import BaseModel


class CameraRecord(BaseModel):

    camera_id: str

    name: str | None = None
    department: str | None = None

    latitude: float | None = None
    longitude: float | None = None

    codec: str | None = None

    width: int | None = None
    height: int | None = None

    reported_fps: float | None = None
    bitrate: int | None = None

    live: bool | None = None

    rtsp_url: str | None = None
    webrtc_url: str | None = None
    hls_url: str | None = None

    raw_metadata: dict[str, Any]