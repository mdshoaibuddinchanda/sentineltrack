import os
import time
import threading
from typing import Dict, List, Optional, Any
import psutil
import torch


class ResourceSnapshot:
    def __init__(self, timestamp: float, cpu_percent: float, rss_mb: float, thread_count: int, vram_alloc_mb: float, vram_reserved_mb: float):
        self.timestamp = timestamp
        self.cpu_percent = cpu_percent
        self.rss_mb = rss_mb
        self.thread_count = thread_count
        self.vram_alloc_mb = vram_alloc_mb
        self.vram_reserved_mb = vram_reserved_mb


class ResourceMonitor:
    """
    Background resource monitor tracking CPU, RAM (RSS), thread count, and CUDA VRAM.
    Computes rolling memory slope (MB/min) to verify zero leak stability.
    """

    def __init__(self, sample_interval_s: float = 1.0, max_history: int = 3600):
        self.sample_interval_s = sample_interval_s
        self.max_history = max_history
        self._process = psutil.Process(os.getpid())
        self._history: List[ResourceSnapshot] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._sample_loop, daemon=True, name="SentinelResourceMonitor")
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def sample_now(self) -> ResourceSnapshot:
        """Collects an instantaneous snapshot of system resource usage."""
        now = time.time()
        cpu = self._process.cpu_percent()
        mem_info = self._process.memory_info()
        rss_mb = mem_info.rss / (1024.0 * 1024.0)
        threads = self._process.num_threads()

        vram_alloc = 0.0
        vram_res = 0.0
        if torch.cuda.is_available():
            try:
                vram_alloc = torch.cuda.memory_allocated() / (1024.0 * 1024.0)
                vram_res = torch.cuda.memory_reserved() / (1024.0 * 1024.0)
            except Exception:
                pass

        snap = ResourceSnapshot(
            timestamp=now,
            cpu_percent=cpu,
            rss_mb=round(rss_mb, 2),
            thread_count=threads,
            vram_alloc_mb=round(vram_alloc, 2),
            vram_reserved_mb=round(vram_res, 2)
        )

        with self._lock:
            self._history.append(snap)
            if len(self._history) > self.max_history:
                self._history.pop(0)

        return snap

    def _sample_loop(self) -> None:
        while self._running:
            self.sample_now()
            time.sleep(self.sample_interval_s)

    def get_summary(self) -> Dict[str, Any]:
        """Calculates resource consumption statistics and memory growth slopes."""
        with self._lock:
            if not self._history:
                latest = self.sample_now()
                return {
                    "cpu_percent": latest.cpu_percent,
                    "rss_mb": latest.rss_mb,
                    "thread_count": latest.thread_count,
                    "vram_alloc_mb": latest.vram_alloc_mb,
                    "vram_reserved_mb": latest.vram_reserved_mb,
                    "rss_slope_mb_per_min": 0.0,
                    "vram_slope_mb_per_min": 0.0
                }

            history_copy = list(self._history)

        start = history_copy[0]
        end = history_copy[-1]
        duration_mins = max(0.01, (end.timestamp - start.timestamp) / 60.0)

        rss_values = [s.rss_mb for s in history_copy]
        vram_values = [s.vram_alloc_mb for s in history_copy]
        cpu_values = [s.cpu_percent for s in history_copy]

        rss_slope = (end.rss_mb - start.rss_mb) / duration_mins
        vram_slope = (end.vram_alloc_mb - start.vram_alloc_mb) / duration_mins

        return {
            "samples_count": len(history_copy),
            "duration_minutes": round(duration_mins, 2),
            "cpu_mean_percent": round(sum(cpu_values) / len(cpu_values), 1),
            "cpu_peak_percent": round(max(cpu_values), 1),
            "rss_start_mb": round(start.rss_mb, 2),
            "rss_end_mb": round(end.rss_mb, 2),
            "rss_peak_mb": round(max(rss_values), 2),
            "rss_slope_mb_per_min": round(rss_slope, 4),
            "vram_start_mb": round(start.vram_alloc_mb, 2),
            "vram_end_mb": round(end.vram_alloc_mb, 2),
            "vram_peak_mb": round(max(vram_values), 2),
            "vram_slope_mb_per_min": round(vram_slope, 4),
            "thread_count": end.thread_count
        }
