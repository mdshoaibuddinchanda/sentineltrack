from dataclasses import dataclass


@dataclass
class VehicleDetection:
    camera_id: str
    pts_ms: float
    stream_epoch: int

    class_id: int
    class_name: str

    confidence: float

    x1: float
    y1: float
    x2: float
    y2: float
