import os
import time
import cv2


os.environ[
    "OPENCV_FFMPEG_CAPTURE_OPTIONS"
] = "rtsp_transport;tcp"


try:
    from .models import FramePacket
except (ImportError, ValueError):
    from streams.models import FramePacket


class RTSPReader:

    def __init__(
        self,
        url: str,
        camera_id: str = "camera_unknown",
        max_backoff: int = 30,
    ):
        self.url = url
        self.camera_id = camera_id
        self.max_backoff = max_backoff
        self.cap = None
        self.stream_epoch = 0
        self.last_pts_ms = -1.0

    def connect(self) -> bool:
        self.cap = cv2.VideoCapture(
            self.url,
            cv2.CAP_FFMPEG,
        )
        return self.cap.isOpened()

    def frames(self):
        """Yields (frame, pts_ms) tuples."""
        backoff = 2

        while True:
            if self.cap is None or not self.cap.isOpened():
                print(f"[RTSP] Connecting to {self.url}")
                if not self.connect():
                    print(f"[RTSP] Connection failed. Retrying in {backoff}s")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self.max_backoff)
                    continue
                backoff = 2

            ok, frame = self.cap.read()
            if not ok:
                print("[RTSP] Frame read failed. Reconnecting.")
                if self.cap is not None:
                    self.cap.release()
                self.cap = None
                time.sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)
                continue

            pts_ms = self.cap.get(cv2.CAP_PROP_POS_MSEC)

            # Loop / reset detection: if PTS jumps backward significantly, increment stream_epoch
            if self.last_pts_ms > 0 and pts_ms < (self.last_pts_ms - 2000.0):
                self.stream_epoch += 1
                print(f"[RTSP] Stream loop detected on {self.camera_id}. New epoch: {self.stream_epoch}")

            self.last_pts_ms = pts_ms
            yield frame, pts_ms

    def packets(self):
        """Yields standardized FramePacket instances."""
        for frame, pts_ms in self.frames():
            yield FramePacket(
                camera_id=self.camera_id,
                pts_ms=pts_ms,
                frame=frame,
                stream_epoch=self.stream_epoch,
            )