from typing import Any
from pydantic import BaseModel, Field


class CameraRecord(BaseModel):

    camera_id: str

    name: str | None = None
    department: str | None = None

    latitude: float | None = None
    longitude: float | None = None
    azimuth: float | None = None
    location_quality: str = "UNKNOWN"

    organization: str | None = None
    source_system: str | None = None
    external_id: str | None = None
    onboarding_method: str | None = None
    coordinate_source: str | None = None
    coordinate_accuracy_m: float | None = None
    coverage_radius_m: float | None = None
    field_of_view_degrees: float | None = None

    codec: str | None = None

    width: int | None = None
    height: int | None = None

    reported_fps: float | None = None
    bitrate: int | None = None

    # Registry enablement defaults to true when a catalogue omits the field.
    # Runtime ONLINE/OFFLINE truth remains a separate worker health signal.
    live: bool = True

    rtsp_url: str | None = None
    webrtc_url: str | None = None
    hls_url: str | None = None

    raw_metadata: dict[str, Any] = Field(default_factory=dict)
