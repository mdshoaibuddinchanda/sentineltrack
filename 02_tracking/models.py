from dataclasses import dataclass, field


@dataclass
class VehicleTrack:
    camera_id: str
    track_id: int
    stream_epoch: int

    first_pts_ms: float
    last_pts_ms: float

    class_id: int
    class_name: str

    confidence: float

    x1: float
    y1: float
    x2: float
    y2: float

    age_frames: int = 1
    trail: list[tuple[float, float]] = field(default_factory=list)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)
