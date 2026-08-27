from dataclasses import dataclass
import numpy as np


@dataclass
class FramePacket:
    camera_id: str
    pts_ms: float
    frame: np.ndarray
    stream_epoch: int = 0
