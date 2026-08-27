import time
from typing import Optional

try:
    from ..registry.database import record_health_event, update_camera_probe_status
except (ImportError, ValueError):
    from registry.database import record_health_event, update_camera_probe_status



class StreamHealthTracker:
    """
    Monitors live stream health, frame timing, and drops for a specific camera.
    """

    def __init__(self, camera_id: str, expected_fps: float = 25.0):
        self.camera_id = camera_id
        self.expected_fps = expected_fps if expected_fps and expected_fps > 0 else 25.0
        self.expected_interval_ms = 1000.0 / self.expected_fps

        self.last_pts_ms: Optional[float] = None
        self.last_wall_time: Optional[float] = None
        self.frame_count: int = 0
        self.fps_start_time: float = time.time()
        self.fps_frame_count: int = 0
        self.current_fps: float = 0.0

    def on_connected(self, latency_ms: float = 0.0) -> None:
        """Called when stream connection is successfully established."""
        record_health_event(
            camera_id=self.camera_id,
            event_type="STREAM_CONNECTED",
            message=f"Connected to stream. First frame latency: {latency_ms:.2f}ms",
        )
        update_camera_probe_status(
            camera_id=self.camera_id,
            stream_status="ONLINE",
            first_frame_latency_ms=latency_ms,
        )

    def on_disconnected(self, reason: str = "") -> None:
        """Called when stream disconnects or fails to read."""
        record_health_event(
            camera_id=self.camera_id,
            event_type="STREAM_DISCONNECTED",
            message=f"Stream disconnected: {reason}",
            pts_ms=self.last_pts_ms,
        )
        update_camera_probe_status(
            camera_id=self.camera_id,
            stream_status="OFFLINE",
        )

    def on_frame(self, pts_ms: float) -> None:
        """
        Processes each received frame timestamp, tracking FPS and drift.
        """
        now = time.time()
        self.frame_count += 1
        self.fps_frame_count += 1

        # Check PTS jump or drop if previous PTS exists
        if self.last_pts_ms is not None:
            delta_pts = pts_ms - self.last_pts_ms
            # If PTS delta is more than 3x expected interval, report a drop/gap
            if delta_pts > 3 * self.expected_interval_ms:
                record_health_event(
                    camera_id=self.camera_id,
                    event_type="FRAME_DROP",
                    message=f"Detected PTS gap: {delta_pts:.1f}ms (expected ~{self.expected_interval_ms:.1f}ms)",
                    pts_ms=pts_ms,
                )

        self.last_pts_ms = pts_ms
        self.last_wall_time = now

        # Update FPS calculation every 2 seconds
        elapsed = now - self.fps_start_time
        if elapsed >= 2.0:
            self.current_fps = self.fps_frame_count / elapsed
            self.fps_start_time = now
            self.fps_frame_count = 0
            update_camera_probe_status(
                camera_id=self.camera_id,
                stream_status="ONLINE",
                measured_fps=round(self.current_fps, 2),
            )
