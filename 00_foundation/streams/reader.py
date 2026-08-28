import os
import time
import cv2
from typing import Optional, Generator, Tuple

os.environ[
    "OPENCV_FFMPEG_CAPTURE_OPTIONS"
] = "rtsp_transport;tcp"

try:
    from .models import FramePacket
except (ImportError, ValueError):
    from streams.models import FramePacket


class RTSPReader:
    """
    Robust stream reader with automatic runtime RTSP -> HLS failover,
    reconnect backoff, and loop/epoch detection.
    """

    def __init__(
        self,
        url: str,
        camera_id: str = "camera_unknown",
        fallback_url: Optional[str] = None,
        max_backoff: int = 30,
        failover_threshold: int = 3,
        recovery_interval_s: float = 60.0
    ):
        self.primary_url = url
        self.fallback_url = fallback_url
        self.camera_id = camera_id
        self.max_backoff = max_backoff
        self.failover_threshold = failover_threshold
        self.recovery_interval_s = recovery_interval_s

        self.active_url = self.primary_url
        self.is_using_fallback = False
        self.consecutive_failures = 0
        self.last_failover_time = 0.0

        self.cap = None
        self.stream_epoch = 0
        self.last_pts_ms = -1.0

    def connect(self) -> bool:
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        self.cap = cv2.VideoCapture(
            self.active_url,
            cv2.CAP_FFMPEG,
        )
        ok = self.cap.isOpened()
        if ok:
            self.consecutive_failures = 0
            return True
        else:
            self.consecutive_failures += 1
            if self._evaluate_failover():
                if self.cap is not None:
                    try:
                        self.cap.release()
                    except Exception:
                        pass
                self.cap = cv2.VideoCapture(self.active_url, cv2.CAP_FFMPEG)
                if self.cap.isOpened():
                    self.consecutive_failures = 0
                    return True
            return False

    def _evaluate_failover(self) -> bool:
        """Switches to fallback URL if primary fails repeatedly."""
        if not self.is_using_fallback and self.fallback_url and self.consecutive_failures >= self.failover_threshold:
            print(f"[Stream] Primary URL failed {self.consecutive_failures} times. Failing over to fallback: {self.fallback_url}")
            self.active_url = self.fallback_url
            self.is_using_fallback = True
            self.last_failover_time = time.time()
            self.consecutive_failures = 0
            return True
        return False

    def _check_primary_recovery(self):
        """Attempts hysteresis recovery back to primary URL after timeout."""
        if self.is_using_fallback and (time.time() - self.last_failover_time) >= self.recovery_interval_s:
            print(f"[Stream] Attempting recovery back to primary stream: {self.primary_url}")
            test_cap = cv2.VideoCapture(self.primary_url, cv2.CAP_FFMPEG)
            if test_cap.isOpened():
                test_cap.release()
                print("[Stream] Primary stream recovered. Switching back to primary.")
                self.active_url = self.primary_url
                self.is_using_fallback = False
                self.consecutive_failures = 0
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
            else:
                test_cap.release()
                self.last_failover_time = time.time()

    def frames(self) -> Generator[Tuple[any, float], None, None]:
        """Yields (frame, pts_ms) tuples."""
        backoff = 2

        while True:
            self._check_primary_recovery()

            if self.cap is None or not self.cap.isOpened():
                if not self.connect():
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self.max_backoff)
                    continue
                backoff = 2

            ok, frame = self.cap.read()
            if not ok:
                self.consecutive_failures += 1
                self._evaluate_failover()
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

            self.last_pts_ms = pts_ms
            yield frame, pts_ms

    def packets(self) -> Generator[FramePacket, None, None]:
        """Yields standardized FramePacket instances."""
        from datetime import datetime, timezone, timedelta
        epoch_anchor_wall_utc = datetime.now(timezone.utc)
        epoch_anchor_pts_ms: Optional[float] = None
        last_epoch = self.stream_epoch

        for frame, pts_ms in self.frames():
            now_utc = datetime.now(timezone.utc)
            if self.stream_epoch != last_epoch or epoch_anchor_pts_ms is None:
                last_epoch = self.stream_epoch
                epoch_anchor_wall_utc = now_utc
                epoch_anchor_pts_ms = pts_ms if pts_ms >= 0 else 0.0

            if pts_ms >= 0:
                delta_ms = max(0.0, pts_ms - epoch_anchor_pts_ms)
                ev_time = epoch_anchor_wall_utc + timedelta(milliseconds=delta_ms)
                ev_source = 'PTS_ANCHORED_ESTIMATE'
                ev_quality = 'MEDIUM'
            else:
                ev_time = now_utc
                ev_source = 'INGEST_TIME'
                ev_quality = 'LOW'

            yield FramePacket(
                camera_id=self.camera_id,
                pts_ms=pts_ms,
                frame=frame,
                stream_epoch=self.stream_epoch,
                ingest_time_utc=now_utc,
                event_time_utc=ev_time,
                event_time_source=ev_source,
                event_time_quality=ev_quality
            )

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
