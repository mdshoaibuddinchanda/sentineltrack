import time
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable

import cv2

import importlib
get_scale_config = importlib.import_module("11_scale_deployment.config").get_scale_config
FairStreamScheduler = importlib.import_module("11_scale_deployment.scheduler").FairStreamScheduler
is_camera_assigned_to_shard = importlib.import_module("11_scale_deployment.shard").is_camera_assigned_to_shard
FramePacket = importlib.import_module("00_foundation.streams.models").FramePacket
RTSPReader = importlib.import_module("00_foundation.streams.reader").RTSPReader
StreamHealthTracker = importlib.import_module("00_foundation.streams.health").StreamHealthTracker


logger = logging.getLogger("sentineltrack.supervisor")


class CameraStreamWorker:
    """
    Supervises a single camera stream with exponential reconnect backoff,
    true source PTS preservation, stream_epoch tracking, and adaptive Base+Burst sampling.
    """

    def __init__(
        self,
        camera_id: str,
        rtsp_url: str,
        fallback_url: Optional[str] = None,
        on_frame_callback: Optional[Callable[[FramePacket], None]] = None,
        base_fps: float = 1.0,
        burst_fps: float = 5.0,
        burst_duration_s: float = 5.0,
        connect_timeout_s: float = 10.0,
        max_backoff_s: float = 30.0,
        failover_threshold: int = 3,
        stale_after_s: float = 20.0,
        recovery_interval_s: float = 300.0,
        http_cookie_provider: Optional[Callable[[str], str]] = None,
    ):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.fallback_url = fallback_url
        self.on_frame_callback = on_frame_callback
        self.base_fps = base_fps
        self.burst_fps = burst_fps
        self.burst_duration_s = burst_duration_s
        self.connect_timeout_s = max(1.0, float(connect_timeout_s))
        self.max_backoff_s = max(1.0, float(max_backoff_s))
        self.failover_threshold = max(1, int(failover_threshold))
        self.stale_after_s = max(5.0, float(stale_after_s))
        self.recovery_interval_s = max(30.0, float(recovery_interval_s))
        self.http_cookie_provider = http_cookie_provider

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # State & Health
        self.stream_epoch = 0
        self.is_connected = False
        self.is_degraded = False
        self.last_frame_time = 0.0
        self.last_pts_ms: Optional[float] = None
        self._connect_started_at = 0.0
        self._health_tracker = StreamHealthTracker(camera_id=camera_id)
        self._latest_jpeg: Optional[bytes] = None
        self._latest_frame: Optional[Any] = None
        self._last_preview_time = 0.0
        self.total_frames_decoded = 0
        self.total_frames_sampled = 0
        self.reconnect_count = 0
        self.burst_until = 0.0
        self._last_sample_time = 0.0

    def trigger_burst(self, duration_s: Optional[float] = None) -> None:
        """Elevates camera sampling to high-frequency burst mode for a duration."""
        dur = duration_s or self.burst_duration_s
        with self._lock:
            self.burst_until = max(self.burst_until, time.time() + dur)

    def is_in_burst(self) -> bool:
        return time.time() < self.burst_until

    def _update_preview(self, frame: Any, now_time: float) -> None:
        """Keep one bounded JPEG snapshot for authenticated human verification."""
        if now_time - self._last_preview_time < 1.0:
            return
        try:
            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                with self._lock:
                    self._latest_jpeg = encoded.tobytes()
                    self._last_preview_time = now_time
        except Exception:
            logger.exception("Preview encoding failed for camera %s", self.camera_id)

    def get_preview(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def get_live_snapshot(self) -> Optional[tuple[Any, float]]:
        """Return the newest decoded frame and its wall-clock timestamp."""
        with self._lock:
            if self._latest_frame is None or self.last_frame_time <= 0:
                return None
            return self._latest_frame.copy(), self.last_frame_time

    def get_current_target_fps(self) -> float:
        return self.burst_fps if self.is_in_burst() else self.base_fps

    def _safe_health_call(self, method_name: str, **kwargs: Any) -> None:
        """Health persistence must never stop analytics ingestion."""
        try:
            getattr(self._health_tracker, method_name)(**kwargs)
        except Exception:
            logger.warning(
                "Camera %s health persistence failed during %s",
                self.camera_id,
                method_name,
                exc_info=True,
            )

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name=f"StreamWorker-{self.camera_id}"
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run_loop(self) -> None:
        backoff_s = 1.0
        max_backoff_s = self.max_backoff_s

        reader = RTSPReader(
            url=self.rtsp_url,
            camera_id=self.camera_id,
            fallback_url=self.fallback_url,
            max_backoff=int(max_backoff_s),
            failover_threshold=self.failover_threshold,
            connect_timeout_s=self.connect_timeout_s,
            recovery_interval_s=self.recovery_interval_s,
            http_cookie_provider=self.http_cookie_provider,
            # This worker owns reconnect/backoff accounting. Keeping a second
            # invisible loop inside RTSPReader previously left cameras stuck
            # as CONNECTING with reconnects=0 while fallback opens queued.
            reconnect_internally=False,
        )

        try:
            while self._running:
                try:
                    self._connect_started_at = time.monotonic()
                    connected = reader.connect()
                    if not connected:
                        self.is_connected = False
                        self.is_degraded = True
                        self.reconnect_count += 1
                        logger.warning(
                            "Camera %s did not connect; retry %s in %.1fs",
                            self.camera_id,
                            self.reconnect_count,
                            backoff_s,
                        )
                        time.sleep(backoff_s)
                        backoff_s = min(max_backoff_s, backoff_s * 1.5)
                        continue

                    # Successfully connected: increment stream epoch & reset backoff
                    with self._lock:
                        self.stream_epoch += 1
                        reader.stream_epoch = self.stream_epoch
                        # Opening a container is not proof that a decodable
                        # video frame is arriving. Mark connected after the
                        # first packet below.
                        self.is_connected = False
                        self.is_degraded = False
                    backoff_s = 1.0
                    logger.info(
                        "Camera [%s] source opened on epoch %s; waiting for first decoded frame",
                        self.camera_id,
                        self.stream_epoch,
                    )

                    # RTSPReader exposes standardized FramePackets through
                    # packets(). Keeping this at the supervisor boundary
                    # preserves stream epoch and event-time metadata.
                    for packet in reader.packets():
                        if not self._running:
                            break

                        now_time = time.time()
                        with self._lock:
                            self.last_frame_time = now_time
                            self.last_pts_ms = packet.pts_ms
                            self._latest_frame = packet.frame
                        self.total_frames_decoded += 1
                        if not self.is_connected:
                            self.is_connected = True
                            self.is_degraded = False
                            self._safe_health_call(
                                "on_connected",
                                latency_ms=max(
                                    0.0,
                                    (time.monotonic() - self._connect_started_at) * 1000.0,
                                ),
                            )
                            logger.info(
                                "Camera [%s] connected with first decoded frame on epoch %s",
                                self.camera_id,
                                self.stream_epoch,
                            )
                        self._safe_health_call("on_frame", pts_ms=packet.pts_ms)
                        self._update_preview(packet.frame, now_time)

                        # Adaptive Base + Burst Sampling
                        target_fps = self.get_current_target_fps()
                        sample_interval = 1.0 / max(0.1, target_fps)

                        if (now_time - self._last_sample_time) >= sample_interval:
                            self._last_sample_time = now_time
                            self.total_frames_sampled += 1

                            # Attach wall-clock event time and ingest timestamp
                            if packet.event_time_utc is None:
                                packet.event_time_utc = datetime.now(timezone.utc)
                                packet.event_time_source = "STREAM_PTS_WALLCLOCK"
                            packet.ingest_time_utc = datetime.now(timezone.utc)

                            if self.on_frame_callback:
                                try:
                                    self.on_frame_callback(packet)
                                except Exception as e:
                                    logger.error(f"Error in on_frame_callback for {self.camera_id}: {e}")

                except Exception as e:
                    logger.warning(f"Stream error on camera {self.camera_id}: {e}")
                    if self.is_connected:
                        self._safe_health_call("on_disconnected", reason=str(e))
                    self.is_connected = False
                    self.is_degraded = True
                    self.reconnect_count += 1
                    time.sleep(backoff_s)
                    backoff_s = min(max_backoff_s, backoff_s * 1.5)
        finally:
            if self.is_connected:
                self._safe_health_call("on_disconnected", reason="worker stopped")
            self.is_connected = False
            reader.release()


class StreamSupervisor:
    """
    Central Stream Orchestration Supervisor managing multi-camera ingestion lifecycle,
    shard filtering, adaptive sampling, and feeding the FairStreamScheduler / AnalyticsWorker.
    """

    def __init__(
        self,
        config=None,
        scheduler: Optional[FairStreamScheduler] = None,
        on_frame_callback: Optional[Callable[[FramePacket], None]] = None,
        http_cookie_provider: Optional[Callable[[str], str]] = None,
        source_diagnostics: Optional[Dict[str, Any]] = None,
    ):
        self.config = config or get_scale_config()
        self.scheduler = scheduler
        self.on_frame_callback = on_frame_callback
        self.http_cookie_provider = http_cookie_provider
        self.source_diagnostics = source_diagnostics or {}
        self._workers: Dict[str, CameraStreamWorker] = {}
        self._lock = threading.Lock()
        self._running = False

    def add_camera(
        self,
        camera_id: str,
        rtsp_url: str,
        fallback_url: Optional[str] = None
    ) -> bool:
        """
        Adds a camera to the supervisor. If sharding is active, checks shard assignment first.
        Returns True if the camera was accepted on this node.
        """
        if not is_camera_assigned_to_shard(camera_id, self.config.shard_index, self.config.shard_count):
            logger.debug(f"Camera {camera_id} assigned to different shard (this shard={self.config.shard_index})")
            return False

        with self._lock:
            if camera_id in self._workers:
                return True

            callback = self._dispatch_frame
            worker = CameraStreamWorker(
                camera_id=camera_id,
                rtsp_url=rtsp_url,
                fallback_url=fallback_url,
                on_frame_callback=callback,
                base_fps=self.config.base_sampling_fps,
                burst_fps=self.config.burst_sampling_fps,
                burst_duration_s=self.config.burst_duration_s,
                connect_timeout_s=float(getattr(self.config, "rtsp_connect_timeout_s", 10.0)),
                max_backoff_s=float(getattr(self.config, "stream_max_backoff_s", 30.0)),
                failover_threshold=int(getattr(self.config, "stream_failover_threshold", 1)),
                stale_after_s=float(getattr(self.config, "stream_stale_after_s", 20.0)),
                recovery_interval_s=float(getattr(self.config, "stream_recovery_interval_s", 300.0)),
                http_cookie_provider=self.http_cookie_provider,
            )
            self._workers[camera_id] = worker

            if self.scheduler:
                self.scheduler.register_camera(camera_id)

            if self._running:
                worker.start()

            return True

    def remove_camera(self, camera_id: str) -> None:
        """Gracefully terminates and unregisters a camera worker."""
        with self._lock:
            worker = self._workers.pop(camera_id, None)
        if worker:
            worker.stop()
        if self.scheduler:
            self.scheduler.unregister_camera(camera_id)

    def trigger_burst(self, camera_id: str, duration_s: Optional[float] = None) -> None:
        """Triggers burst sampling on a specific camera feed upon target/vehicle detection."""
        with self._lock:
            worker = self._workers.get(camera_id)
        if worker:
            worker.trigger_burst(duration_s)

    def _dispatch_frame(self, packet: FramePacket) -> None:
        """Routes sampled frame packet to scheduler or callback."""
        # AnalyticsWorker.enqueue_frame already writes to the same scheduler.
        # Choose one delivery path so every sampled frame is enqueued exactly once.
        if self.on_frame_callback:
            self.on_frame_callback(packet)
        elif self.scheduler:
            self.scheduler.enqueue_frame(packet)

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            for worker in self._workers.values():
                worker.start()
            logger.info(f"StreamSupervisor started with {len(self._workers)} camera workers.")

    def stop(self) -> None:
        with self._lock:
            self._running = False
            workers = list(self._workers.values())
        for w in workers:
            w.stop()
        logger.info("StreamSupervisor stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Returns aggregate stream health, active feeds, decode/sampled FPS."""
        now = time.time()
        monotonic_now = time.monotonic()
        with self._lock:
            total = len(self._workers)
            def frame_is_fresh(worker: CameraStreamWorker) -> bool:
                return (
                    worker.last_frame_time > 0
                    and (now - worker.last_frame_time) <= worker.stale_after_s
                )

            def connection_timeout_code(worker: CameraStreamWorker) -> Optional[str]:
                if worker._connect_started_at <= 0:
                    return None
                elapsed = monotonic_now - worker._connect_started_at
                deadline = max(worker.stale_after_s, worker.connect_timeout_s * 2.0)
                if elapsed <= deadline:
                    return None
                if worker.last_frame_time <= 0:
                    return (
                        "FIRST_FRAME_TIMEOUT"
                        if worker.stream_epoch > 0
                        else "SOURCE_OPEN_TIMEOUT"
                    )
                return None

            def worker_is_degraded(worker: CameraStreamWorker) -> bool:
                return bool(
                    worker.is_degraded
                    or (
                        worker.is_connected
                        and worker.last_frame_time > 0
                        and not frame_is_fresh(worker)
                    )
                    or connection_timeout_code(worker)
                )

            connected = sum(
                1 for w in self._workers.values()
                if w.is_connected and frame_is_fresh(w)
            )
            degraded = sum(
                1
                for w in self._workers.values()
                if worker_is_degraded(w)
            )
            total_decoded = sum(w.total_frames_decoded for w in self._workers.values())
            total_sampled = sum(w.total_frames_sampled for w in self._workers.values())
            reconnects = sum(w.reconnect_count for w in self._workers.values())

            camera_states = {}
            for cid, w in self._workers.items():
                fresh = frame_is_fresh(w)
                runtime_connected = bool(w.is_connected and fresh)
                timeout_code = connection_timeout_code(w)
                runtime_degraded = worker_is_degraded(w)
                issue_code = timeout_code
                issue_message = None
                if timeout_code == "FIRST_FRAME_TIMEOUT":
                    issue_message = (
                        "The source opened but did not yield a decodable first frame "
                        "within the bounded startup window; automatic retry is active."
                    )
                elif timeout_code == "SOURCE_OPEN_TIMEOUT":
                    issue_message = (
                        "Opening the source exceeded the bounded startup window; "
                        "automatic retry/failover is active."
                    )
                elif w.is_connected and w.last_frame_time > 0 and not fresh:
                    issue_code = "STALE_FRAME"
                    issue_message = (
                        "The source stopped delivering fresh decoded frames; "
                        "automatic retry/failover is active."
                    )
                elif w.is_degraded:
                    issue_code = "RECONNECTING"
                    issue_message = "The source failed and is in bounded reconnect backoff."
                camera_states[cid] = {
                    "connected": runtime_connected,
                    "degraded": runtime_degraded,
                    "epoch": w.stream_epoch,
                    "in_burst": w.is_in_burst(),
                    "target_fps": w.get_current_target_fps(),
                    "frames_decoded": w.total_frames_decoded,
                    "frames_sampled": w.total_frames_sampled,
                    "reconnects": w.reconnect_count,
                    "last_frame_s_ago": round(now - w.last_frame_time, 2) if w.last_frame_time > 0 else None,
                    "last_pts_ms": w.last_pts_ms,
                    "preview_available": w.get_preview() is not None,
                    "connection_issue_code": issue_code,
                    "connection_issue_message": issue_message,
                }

            return {
                "running": self._running,
                "total_cameras": total,
                "connected_cameras": connected,
                "degraded_cameras": degraded,
                "total_frames_decoded": total_decoded,
                "total_frames_sampled": total_sampled,
                "total_reconnects": reconnects,
                "shard_index": self.config.shard_index,
                "shard_count": self.config.shard_count,
                "cameras": camera_states,
                "source_diagnostics": dict(self.source_diagnostics),
            }

    def get_preview(self, camera_id: str) -> Optional[bytes]:
        """Return the latest bounded camera snapshot, if a frame was decoded."""
        with self._lock:
            worker = self._workers.get(camera_id)
        return worker.get_preview() if worker else None

    def get_live_snapshot(self, camera_id: str) -> Optional[tuple[Any, float]]:
        """Return the newest decoded frame for a live authenticated relay."""
        with self._lock:
            worker = self._workers.get(camera_id)
        if worker is None or not worker.is_connected:
            return None
        snapshot = worker.get_live_snapshot()
        if snapshot is None:
            return None
        frame, frame_time = snapshot
        if (time.time() - frame_time) > worker.stale_after_s:
            return None
        return frame, frame_time
