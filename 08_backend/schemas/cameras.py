from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CameraResponse(BaseModel):
    camera_id: str
    name: Optional[str] = None
    department: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    azimuth: Optional[float] = None
    location_quality: str = "VERIFIED"
    live: bool = True
    stream_status: str = "ONLINE"
    measured_fps: Optional[float] = None
    last_checked: Optional[datetime] = None
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


class CameraNearbyQuery(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    radius_m: float = Field(default=5000.0, ge=100.0, le=50000.0)
