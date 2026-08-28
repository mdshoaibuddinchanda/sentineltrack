import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from collections import deque

import importlib
get_scale_config = importlib.import_module("11_scale_deployment.config").get_scale_config
BoundedStreamQueue = importlib.import_module("00_foundation.streams.bounded_stream_queue").BoundedStreamQueue



class FairStreamScheduler:
    """
    Fair Multi-Camera Stream Scheduler with Deficit Round-Robin turn-taking,
    bounded per-camera queues, and real-time staleness deadline enforcement.
    """

    def __init__(self, config=None):
        self.config = config or get_scale_config()
        self._lock = threading.RLock()
        self._camera_queues: Dict[str, BoundedStreamQueue] = {}
        self._camera_order: List[str] = []
        self._round_robin_idx = 0

        # Telemetry & Fairness Metrics
        self._camera_last_processed: Dict[str, float] = {}
        self._camera_max_starvation_s: Dict[str, float] = {}
        self._camera_sample_counts: Dict[str, int] = {}
        self._total_ingested = 0
        self._total_processed = 0
        self._total_dropped_stale = 0
        self._total_dropped_queue = 0

    def register_camera(self, camera_id: str, queue_size: Optional[int] = None) -> BoundedStreamQueue:
        """Registers a camera with a dedicated bounded stream queue."""
        q_size = queue_size or self.config.queue_max_size
        with self._lock:
            if camera_id not in self._camera_queues:
                self._camera_queues[camera_id] = BoundedStreamQueue(maxsize=q_size)
                self._camera_order.append(camera_id)
                self._camera_last_processed[camera_id] = time.time()
                self._camera_max_starvation_s[camera_id] = 0.0
                self._camera_sample_counts[camera_id] = 0
            return self._camera_queues[camera_id]

    def unregister_camera(self, camera_id: str) -> None:
        """Unregisters an offline or removed camera and cleans up memory."""
        with self._lock:
            self._camera_queues.pop(camera_id, None)
            if camera_id in self._camera_order:
                self._camera_order.remove(camera_id)
            self._camera_last_processed.pop(camera_id, None)
            self._camera_max_starvation_s.pop(camera_id, None)
            self._camera_sample_counts.pop(camera_id, None)
            if self._round_robin_idx >= len(self._camera_order):
                self._round_robin_idx = 0

    def enqueue_frame(self, frame_packet: Any) -> bool:
        """
        Pushes a FramePacket to the camera queue with latest-frame eviction on full queue.
        Returns True if queued, False if dropped due to queue eviction.
        """
        cid = getattr(frame_packet, "camera_id", "unknown")
        with self._lock:
            if cid not in self._camera_queues:
                self.register_camera(cid)
            bq = self._camera_queues[cid]
            self._total_ingested += 1

        # Put packet with latest-frame retention
        ok = bq.put_latest(frame_packet)
        if not ok:
            with self._lock:
                self._total_dropped_queue += 1
        return ok

    def fetch_batch(
        self,
        max_batch_size: Optional[int] = None,
        max_wait_ms: Optional[float] = None
    ) -> List[Any]:
        """
        Extracts a micro-batch of frames fairly across all active cameras using Deficit Round-Robin.
        Enforces staleness drop policy (discards frames older than max_staleness_ms).
        """
        batch_limit = max_batch_size or self.config.micro_batch_size
        wait_s = (max_wait_ms or self.config.max_batch_wait_ms) / 1000.0
        max_staleness_ms = self.config.max_staleness_ms

        deadline = time.time() + wait_s
        batch: List[Any] = []

        while len(batch) < batch_limit:
            with self._lock:
                active_count = len(self._camera_order)
                if active_count == 0:
                    break

                start_idx = self._round_robin_idx
                checked = 0
                found_packet = False

                while checked < active_count and len(batch) < batch_limit:
                    curr_idx = (start_idx + checked) % active_count
                    cid = self._camera_order[curr_idx]
                    bq = self._camera_queues.get(cid)

                    if bq and bq.qsize() > 0:
                        try:
                            pkt = bq.get(block=False)
                            now_time = time.time()

                            # 1. Staleness Check
                            stale = False
                            if hasattr(pkt, "ingest_time_utc") and pkt.ingest_time_utc:
                                now_utc = datetime.now(timezone.utc)
                                age_ms = (now_utc - pkt.ingest_time_utc).total_seconds() * 1000.0
                                if age_ms > max_staleness_ms:
                                    stale = True
                                    self._total_dropped_stale += 1

                            if not stale:
                                batch.append(pkt)
                                found_packet = True
                                # Update fairness telemetry
                                last_time = self._camera_last_processed.get(cid, now_time)
                                gap = now_time - last_time
                                max_prev = self._camera_max_starvation_s.get(cid, 0.0)
                                self._camera_max_starvation_s[cid] = max(max_prev, gap)
                                self._camera_last_processed[cid] = now_time
                                self._camera_sample_counts[cid] = self._camera_sample_counts.get(cid, 0) + 1
                                self._total_processed += 1

                            # Advance round robin pointer past this camera
                            self._round_robin_idx = (curr_idx + 1) % active_count
                        except Exception:
                            pass

                    checked += 1

            if batch or time.time() >= deadline:
                break
            time.sleep(0.001)

        return batch

    def get_metrics(self) -> Dict[str, Any]:
        """Returns comprehensive real-time scheduler fairness and queue metrics."""
        now = time.time()
        with self._lock:
            active_cams = list(self._camera_order)
            starvation_gaps = []
            queue_depths = {}

            for cid in active_cams:
                last_proc = self._camera_last_processed.get(cid, now)
                gap = now - last_proc
                starvation_gaps.append(gap)
                bq = self._camera_queues.get(cid)
                queue_depths[cid] = {
                    "qsize": bq.qsize() if bq else 0,
                    "maxsize": getattr(bq, "maxsize", self.config.queue_max_size)
                }


            max_starv = max(starvation_gaps) if starvation_gaps else 0.0
            med_starv = (
                sorted(starvation_gaps)[len(starvation_gaps) // 2]
                if starvation_gaps
                else 0.0
            )

            return {
                "active_camera_count": len(active_cams),
                "total_ingested": self._total_ingested,
                "total_processed": self._total_processed,
                "total_dropped_stale": self._total_dropped_stale,
                "total_dropped_queue": self._total_dropped_queue,
                "max_starvation_interval_s": round(max_starv, 4),
                "median_starvation_interval_s": round(med_starv, 4),
                "queue_depths": queue_depths,
                "camera_samples": dict(self._camera_sample_counts),
            }
