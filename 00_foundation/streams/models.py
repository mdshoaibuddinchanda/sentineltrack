from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import numpy as np


@dataclass
class FramePacket:
    camera_id: str
    pts_ms: float
    frame: np.ndarray
    stream_epoch: int = 0
    ingest_time_utc: Optional[datetime] = None
    event_time_utc: Optional[datetime] = None
    event_time_source: Optional[str] = None
    event_time_quality: Optional[str] = None
