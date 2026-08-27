import time
import av
import numpy as np
from typing import Generator, Optional, Tuple

try:
    from .models import FramePacket
except (ImportError, ValueError):
    from streams.models import FramePacket


class PyAVReader:
    """
    True-PTS stream reader using PyAV / LibAV.
    Decodes packets and computes millisecond source PTS directly from frame.pts * frame.time_base.
    """

    def __init__(
        self,
        url: str,
        camera_id: str = 'camera_unknown',
        max_backoff: int = 30,
        rtsp_transport: str = 'tcp',
        timeout_seconds: float = 5.0
    ):
        self.url = url
        self.camera_id = camera_id
        self.max_backoff = max_backoff
        self.rtsp_transport = rtsp_transport
        self.timeout_seconds = timeout_seconds

        self.container: Optional[av.container.InputContainer] = None
        self.stream_epoch = 0
        self.last_pts_ms = -1.0

    def connect(self) -> bool:
        options = {
            'rtsp_transport': self.rtsp_transport,
            'stimeout': str(int(self.timeout_seconds * 1000000)),
            'buffer_size': '1048576'
        }
        try:
            self.container = av.open(self.url, mode='r', options=options, timeout=self.timeout_seconds)
            return True
        except Exception as e:
            self.container = None
            return False

    def frames(self) -> Generator[Tuple[np.ndarray, float], None, None]:
        backoff = 2
        while True:
            if self.container is None:
                if not self.connect():
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self.max_backoff)
                    continue
                backoff = 2

            try:
                video_stream = self.container.streams.video[0]
                time_base = video_stream.time_base
                for frame in self.container.decode(video=0):
                    # Compute source presentation timestamp (PTS)
                    if frame.pts is not None and time_base is not None:
                        pts_ms = float(frame.pts * time_base * 1000.0)
                    else:
                        # Fallback to estimated frame timing
                        pts_ms = (self.last_pts_ms + 40.0) if self.last_pts_ms >= 0 else 0.0

                    # Loop / epoch reset detection
                    if self.last_pts_ms > 0 and pts_ms < (self.last_pts_ms - 2000.0):
                        self.stream_epoch += 1

                    self.last_pts_ms = pts_ms
                    frame_bgr = frame.to_ndarray(format='bgr24')
                    yield frame_bgr, pts_ms

            except Exception:
                if self.container is not None:
                    try:
                        self.container.close()
                    except Exception:
                        pass
                self.container = None
                time.sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)

    def packets(self) -> Generator[FramePacket, None, None]:
        for frame, pts_ms in self.frames():
            yield FramePacket(
                camera_id=self.camera_id,
                pts_ms=pts_ms,
                frame=frame,
                stream_epoch=self.stream_epoch
            )

    def close(self):
        if self.container is not None:
            try:
                self.container.close()
            except Exception:
                pass
            self.container = None
