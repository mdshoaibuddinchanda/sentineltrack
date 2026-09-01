import os
import time
import logging
import threading
import cv2
from typing import Callable, Optional, Generator, Tuple

logger = logging.getLogger("sentineltrack.stream_reader")

_CAPTURE_OPTIONS_LOCK = threading.Lock()

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
        recovery_interval_s: float = 60.0,
        connect_timeout_s: Optional[float] = None,
        http_cookie_provider: Optional[Callable[[str], str]] = None,
    ):
        self.primary_url = url
        self.fallback_url = fallback_url
        self.camera_id = camera_id
        self.max_backoff = max_backoff
        self.failover_threshold = failover_threshold
        self.recovery_interval_s = recovery_interval_s
        configured_timeout = connect_timeout_s
        if configured_timeout is None:
            configured_timeout = os.getenv("RTSP_CONNECT_TIMEOUT", "10")
        self.connect_timeout_s = max(1.0, float(configured_timeout))
        self.http_cookie_provider = http_cookie_provider

        self.active_url = self.primary_url
        self.is_using_fallback = False
        self.consecutive_failures = 0
        self.last_failover_time = 0.0

        self.cap = None
        self.stream_epoch = 0
        self.last_pts_ms = -1.0

    def _ffmpeg_capture_options(self, url: str) -> str:
        options: list[str] = []
        if url.lower().startswith("rtsp://"):
            options.append("rtsp_transport;tcp")
        if url.lower().startswith(("http://", "https://")) and self.http_cookie_provider:
            try:
                cookies = self.http_cookie_provider(url)
            except Exception:
                logger.warning(
                    "Could not obtain the authorized media session for camera %s",
                    self.camera_id,
                    exc_info=True,
                )
                cookies = ""
            if cookies:
                options.append(f"cookies;{cookies}")
        return "|".join(options)

    def _open_capture(self, url: str):
        """Open a capture with bounded FFmpeg open/read timeouts."""
        timeout_ms = int(self.connect_timeout_s * 1000)
        params = [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            timeout_ms,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            timeout_ms,
        ]
        options = self._ffmpeg_capture_options(url)
        # OpenCV reads this process-global variable while VideoCapture is
        # constructed. Serialize that small critical section so 30 camera
        # threads cannot leak one camera's cookie/options into another open.
        with _CAPTURE_OPTIONS_LOCK:
            previous = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS")
            if options:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = options
            else:
                os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
            try:
                try:
                    return cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)
                except (TypeError, cv2.error):
                    logger.warning(
                        "OpenCV build does not support bounded capture parameters for camera %s",
                        self.camera_id,
                    )
                    return cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            finally:
                if previous is None:
                    os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
                else:
                    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = previous

    def connect(self) -> bool:
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        self.cap = self._open_capture(self.active_url)
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
                self.cap = self._open_capture(self.active_url)
                if self.cap.isOpened():
                    self.consecutive_failures = 0
                    return True
            return False

    def _evaluate_failover(self) -> bool:
        """Switches to fallback URL if primary fails repeatedly."""
        if not self.is_using_fallback and self.fallback_url and self.consecutive_failures >= self.failover_threshold:
            logger.warning(
                "Camera %s primary source failed %s times; switching to configured fallback",
                self.camera_id,
                self.consecutive_failures,
            )
            self.active_url = self.fallback_url
            self.is_using_fallback = True
            self.last_failover_time = time.time()
            self.consecutive_failures = 0
            return True
        return False

    def _check_primary_recovery(self):
        """Attempts hysteresis recovery back to primary URL after timeout."""
        if self.is_using_fallback and (time.time() - self.last_failover_time) >= self.recovery_interval_s:
            logger.info("Camera %s attempting recovery to its primary source", self.camera_id)
            test_cap = self._open_capture(self.primary_url)
            recovered = False
            if test_cap.isOpened():
                try:
                    recovered, _ = test_cap.read()
                except Exception:
                    recovered = False
            test_cap.release()
            if recovered:
                logger.info("Camera %s primary stream recovered", self.camera_id)
                self.active_url = self.primary_url
                self.is_using_fallback = False
                self.consecutive_failures = 0
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
            else:
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
