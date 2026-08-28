import time
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable

import importlib
get_scale_config = importlib.import_module("11_scale_deployment.config").get_scale_config
FairStreamScheduler = importlib.import_module("11_scale_deployment.scheduler").FairStreamScheduler
is_camera_assigned_to_shard = importlib.import_module("11_scale_deployment.shard").is_camera_assigned_to_shard
FramePacket = importlib.import_module("00_foundation.streams.models").FramePacket
RTSPReader = importlib.import_module("00_foundation.streams.reader").RTSPReader


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
        burst_duration_s: float = 5.0
    ):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.fallback_url = fallback_url
        self.on_frame_callback = on_frame_callback
        self.base_fps = base_fps
        self.burst_fps = burst_fps
        self.burst_duration_s = burst_duration_s

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # State & Health
        self.stream_epoch = 0
        self.is_connected = False
        self.is_degraded = False
        self.last_frame_time = 0.0
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

    def get_current_target_fps(self) -> float:
        return self.burst_fps if self.is_in_burst() else self.base_fps

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
        max_backoff_s = 30.0

        reader = RTSPReader(
            url=self.rtsp_url,
            camera_id=self.camera_id,
            fallback_url=self.fallback_url,
            max_backoff=int(max_backoff_s)
        )

        while self._running:
            try:
                connected = reader.connect()
                if not connected:
                    self.is_connected = False
                    self.is_degraded = True
                    self.reconnect_count += 1
                    time.sleep(backoff_s)
                    backoff_s = min(max_backoff_s, backoff_s * 1.5)
                    continue

                # Successfully connected: increment stream epoch & reset backoff
                with self._lock:
                    self.stream_epoch += 1
                    reader.stream_epoch = self.stream_epoch
                    self.is_connected = True
                    self.is_degraded = False
                backoff_s = 1.0
                logger.info(f"Camera [{self.camera_id}] connected on epoch {self.stream_epoch}")

                for packet in reader.read_frames():
                    if not self._running:
                        break

                    now_time = time.time()
                    self.last_frame_time = now_time
                    self.total_frames_decoded += 1

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
                self.is_connected = False
                self.is_degraded = True
                self.reconnect_count += 1
                time.sleep(backoff_s)
                backoff_s = min(max_backoff_s, backoff_s * 1.5)


class StreamSupervisor:
    """
    Central Stream Orchestration Supervisor managing multi-camera ingestion lifecycle,
    shard filtering, adaptive sampling, and feeding the FairStreamScheduler / AnalyticsWorker.
    """

    def __init__(
        self,
        config=None,
        scheduler: Optional[FairStreamScheduler] = None,
        on_frame_callback: Optional[Callable[[FramePacket], None]] = None
    ):
        self.config = config or get_scale_config()
        self.scheduler = scheduler
        self.on_frame_callback = on_frame_callback
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
                burst_duration_s=self.config.burst_duration_s
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
        if self.scheduler:
            self.scheduler.enqueue_frame(packet)
        if self.on_frame_callback:
            self.on_frame_callback(packet)

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
        with self._lock:
            total = len(self._workers)
            connected = sum(1 for w in self._workers.values() if w.is_connected)
            degraded = sum(1 for w in self._workers.values() if w.is_degraded)
            total_decoded = sum(w.total_frames_decoded for w in self._workers.values())
            total_sampled = sum(w.total_frames_sampled for w in self._workers.values())
            reconnects = sum(w.reconnect_count for w in self._workers.values())

            camera_states = {}
            for cid, w in self._workers.items():
                camera_states[cid] = {
                    "connected": w.is_connected,
                    "degraded": w.is_degraded,
                    "epoch": w.stream_epoch,
                    "in_burst": w.is_in_burst(),
                    "target_fps": w.get_current_target_fps(),
                    "frames_decoded": w.total_frames_decoded,
                    "frames_sampled": w.total_frames_sampled,
                    "reconnects": w.reconnect_count,
                    "last_frame_s_ago": round(now - w.last_frame_time, 2) if w.last_frame_time > 0 else None
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
                "cameras": camera_states
            }
