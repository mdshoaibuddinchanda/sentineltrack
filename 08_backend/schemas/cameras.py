from datetime import datetime
from enum import Enum
import math
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CAMERA_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
SENSITIVE_METADATA_KEYS = {"password", "passwd", "secret", "token", "api_key", "apikey", "cookie", "authorization"}


class LocationQualityEnum(str, Enum):
    VERIFIED = "VERIFIED"
    APPROXIMATE = "APPROXIMATE"
    UNKNOWN = "UNKNOWN"


class CameraImportMode(str, Enum):
    CREATE_ONLY = "CREATE_ONLY"
    UPSERT = "UPSERT"


def _contains_sensitive_metadata(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).strip().lower() in SENSITIVE_METADATA_KEYS:
                return True
            if _contains_sensitive_metadata(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_metadata(item) for item in value)
    return False


class CameraRegistryInput(BaseModel):
    """Normalized operator/VMS camera record; credentials are intentionally excluded."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    camera_id: str = Field(..., min_length=1, max_length=128)
    name: Optional[str] = Field(default=None, max_length=256)
    department: Optional[str] = Field(default=None, max_length=256)
    organization: Optional[str] = Field(default=None, max_length=256)
    source_system: str = Field(default="MANUAL", min_length=1, max_length=128)
    external_id: Optional[str] = Field(default=None, max_length=256)

    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    azimuth: Optional[float] = Field(default=None, ge=0.0, lt=360.0)
    location_quality: LocationQualityEnum = LocationQualityEnum.UNKNOWN
    coordinate_source: Optional[str] = Field(default=None, max_length=512)
    coordinate_accuracy_m: Optional[float] = Field(default=None, gt=0.0, le=100000.0)
    coverage_radius_m: Optional[float] = Field(default=None, gt=0.0, le=10000.0)
    field_of_view_degrees: Optional[float] = Field(default=None, gt=0.0, le=360.0)

    rtsp_url: Optional[str] = Field(default=None, max_length=2048)
    hls_url: Optional[str] = Field(default=None, max_length=2048)
    webrtc_url: Optional[str] = Field(default=None, max_length=2048)
    live: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("camera_id")
    @classmethod
    def validate_camera_id(cls, value: str) -> str:
        if not CAMERA_ID_PATTERN.fullmatch(value):
            raise ValueError("camera_id may contain only letters, numbers, dot, underscore, colon, and hyphen")
        return value

    @field_validator("latitude", "longitude", "azimuth", "coordinate_accuracy_m", "coverage_radius_m", "field_of_view_degrees")
    @classmethod
    def validate_finite_numbers(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and not math.isfinite(value):
            raise ValueError("numeric values must be finite")
        return value

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, value: Optional[str]) -> Optional[str]:
        return cls._validate_stream_url(value, {"rtsp", "rtsps"}, "RTSP")

    @field_validator("hls_url")
    @classmethod
    def validate_hls_url(cls, value: Optional[str]) -> Optional[str]:
        return cls._validate_stream_url(value, {"http", "https"}, "HLS")

    @field_validator("webrtc_url")
    @classmethod
    def validate_webrtc_url(cls, value: Optional[str]) -> Optional[str]:
        return cls._validate_stream_url(value, {"http", "https"}, "WebRTC/WHEP")

    @staticmethod
    def _validate_stream_url(value: Optional[str], schemes: set[str], label: str) -> Optional[str]:
        if value is None or not value.strip():
            return None
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in schemes or not parsed.hostname:
            raise ValueError(f"{label} URL has an unsupported scheme or missing host")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(f"{label} credentials must use an external secret reference, not a URL")
        return value

    @field_validator("metadata")
    @classmethod
    def reject_secrets_in_metadata(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if _contains_sensitive_metadata(value):
            raise ValueError("metadata must not contain passwords, tokens, cookies, or API keys")
        return value

    @model_validator(mode="after")
    def validate_location_provenance(self):
        has_lat = self.latitude is not None
        has_lon = self.longitude is not None
        if has_lat != has_lon:
            raise ValueError("latitude and longitude must be supplied together")
        if not has_lat:
            if self.location_quality != LocationQualityEnum.UNKNOWN:
                raise ValueError("location_quality must be UNKNOWN when coordinates are absent")
            if any(value is not None for value in (self.coordinate_accuracy_m, self.coverage_radius_m, self.field_of_view_degrees, self.azimuth)):
                raise ValueError("camera geometry requires latitude and longitude")
        elif not self.coordinate_source:
            raise ValueError("coordinate_source is required whenever coordinates are supplied")
        if self.external_id is None:
            self.external_id = self.camera_id
        return self


class CameraUpdateRequest(BaseModel):
    """Patch model; the service validates the merged complete record."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, max_length=256)
    department: Optional[str] = Field(default=None, max_length=256)
    organization: Optional[str] = Field(default=None, max_length=256)
    source_system: Optional[str] = Field(default=None, min_length=1, max_length=128)
    external_id: Optional[str] = Field(default=None, max_length=256)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    azimuth: Optional[float] = Field(default=None, ge=0.0, lt=360.0)
    location_quality: Optional[LocationQualityEnum] = None
    coordinate_source: Optional[str] = Field(default=None, max_length=512)
    coordinate_accuracy_m: Optional[float] = Field(default=None, gt=0.0, le=100000.0)
    coverage_radius_m: Optional[float] = Field(default=None, gt=0.0, le=10000.0)
    field_of_view_degrees: Optional[float] = Field(default=None, gt=0.0, le=360.0)
    rtsp_url: Optional[str] = Field(default=None, max_length=2048)
    hls_url: Optional[str] = Field(default=None, max_length=2048)
    webrtc_url: Optional[str] = Field(default=None, max_length=2048)
    live: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class CameraBulkImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cameras: List[CameraRegistryInput] = Field(..., min_length=1, max_length=500)
    mode: CameraImportMode = CameraImportMode.CREATE_ONLY
    dry_run: bool = True


class CameraImportItemResult(BaseModel):
    row: int
    camera_id: str
    status: str
    message: str


class CameraBulkImportResponse(BaseModel):
    dry_run: bool
    received: int
    valid: int
    created: int
    updated: int
    skipped: int
    worker_started: int = 0
    worker_restart_required: int = 0
    items: List[CameraImportItemResult] = Field(default_factory=list)


class CameraMutationResponse(BaseModel):
    camera: "CameraResponse"
    created: bool
    worker_status: str


class CameraGapAnalysisResponse(BaseModel):
    generated_at_utc: datetime
    total_cameras: int
    geolocated_cameras: int
    verified_coordinates: int
    approximate_coordinates: int
    unknown_coordinates: int
    missing_coordinates: int
    missing_coordinate_source: int
    missing_department: int
    missing_organization: int
    missing_azimuth: int
    missing_stream_source: int
    enabled_cameras: int
    source_systems: Dict[str, int] = Field(default_factory=dict)
    organizations: Dict[str, int] = Field(default_factory=dict)
    departments: Dict[str, int] = Field(default_factory=dict)
    isolated_camera_ids: List[str] = Field(default_factory=list)
    isolation_radius_m: float
    limitations: List[str] = Field(default_factory=list)


class CoverageAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area_of_interest: Dict[str, Any]
    default_coverage_radius_m: float = Field(default=100.0, ge=10.0, le=10000.0)
    include_approximate: bool = False

    @field_validator("area_of_interest")
    @classmethod
    def validate_polygon(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        geometry = value.get("geometry") if value.get("type") == "Feature" else value
        if not isinstance(geometry, dict) or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("area_of_interest must be a GeoJSON Polygon or MultiPolygon")
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError("area_of_interest has no coordinates")
        if len(str(value)) > 1_000_000:
            raise ValueError("area_of_interest is too large")
        return geometry


class CoverageAnalysisResponse(BaseModel):
    generated_at_utc: datetime
    eligible_camera_count: int
    area_of_interest_m2: float
    covered_area_m2: float
    uncovered_area_m2: float
    coverage_percent: float
    default_coverage_radius_m: float
    include_approximate: bool
    coverage_model: str
    geojson: Dict[str, Any]
    limitations: List[str] = Field(default_factory=list)


class VMSConnectorStatus(BaseModel):
    connector_id: str
    connector_type: str
    enabled: bool
    organization: str
    source_system: str
    camera_id_prefix: str
    endpoint_host: Optional[str] = None
    credential_env_configured: bool = False
    ready: bool
    readiness_message: str


class VMSConnectorListResponse(BaseModel):
    config_path: str
    items: List[VMSConnectorStatus] = Field(default_factory=list)
    total: int


class VMSConnectorSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = True
    mode: CameraImportMode = CameraImportMode.UPSERT


class CameraResponse(BaseModel):
    camera_id: str
    name: Optional[str] = None
    department: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    azimuth: Optional[float] = None
    location_quality: str = "UNKNOWN"
    organization: Optional[str] = None
    source_system: Optional[str] = None
    external_id: Optional[str] = None
    onboarding_method: Optional[str] = None
    coordinate_source: Optional[str] = None
    coordinate_accuracy_m: Optional[float] = None
    coverage_radius_m: Optional[float] = None
    field_of_view_degrees: Optional[float] = None
    live: bool = True
    stream_status: str = "ONLINE"
    measured_fps: Optional[float] = None
    last_checked: Optional[datetime] = None
    source_configured: bool = False
    frames_decoded: int = 0
    frames_sampled: int = 0
    reconnects: int = 0
    last_frame_s_ago: Optional[float] = None
    connection_issue_code: Optional[str] = None
    connection_issue_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CameraListResponse(BaseModel):
    items: List[CameraResponse]
    total: int


class CameraHealthResponse(BaseModel):
    camera_id: str
    stream_status: str
    first_frame_latency_ms: Optional[float] = None
    last_pts_ms: Optional[float] = None
    last_checked: Optional[datetime] = None
    source_configured: bool = False
    connected: bool = False
    frames_decoded: int = 0
    frames_sampled: int = 0
    reconnects: int = 0
    last_frame_s_ago: Optional[float] = None
    connection_issue_code: Optional[str] = None
    connection_issue_message: Optional[str] = None


class CameraNearbyQuery(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    radius_m: float = Field(default=5000.0, ge=100.0, le=50000.0)


CameraMutationResponse.model_rebuild()
