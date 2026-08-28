import time
import math
import threading
from typing import Dict, Any, List
from collections import deque
import psutil

try:
    import torch
except ImportError:
    torch = None



class MetricsCollector:
    """Thread-safe operational and performance metrics collector for SentinelTrack."""

    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.total_requests = 0
        self.total_errors = 0
        self.active_requests = 0
        self.active_websocket_clients = 0
        self.active_camera_workers = 0
        self.total_frames_ingested = 0
        self.total_frames_dropped = 0
        self.total_frames_dropped_stale = 0
        self.total_vehicle_detections = 0
        self.total_plate_inferences = 0
        self.total_ocr_consensus = 0
        self.total_sightings_persisted = 0
        self.total_alerts_generated = 0
        self.total_routes_computed = 0
        self._request_latencies: deque = deque(maxlen=2000)

    def inc_requests(self):
        with self._lock:
            self.total_requests += 1

    def inc_active_requests(self):
        with self._lock:
            self.active_requests += 1

    def dec_active_requests(self):
        with self._lock:
            self.active_requests = max(0, self.active_requests - 1)

    def record_request_latency(self, duration_ms: float):
        with self._lock:
            self._request_latencies.append(duration_ms)

    def inc_errors(self):
        with self._lock:
            self.total_errors += 1

    def set_ws_clients(self, count: int):
        with self._lock:
            self.active_websocket_clients = count

    def set_camera_workers(self, count: int):
        with self._lock:
            self.active_camera_workers = count

    def inc_frames(self, ingested: int = 1, dropped: int = 0, stale: int = 0):
        with self._lock:
            self.total_frames_ingested += ingested
            self.total_frames_dropped += dropped
            self.total_frames_dropped_stale += stale

    def inc_analytics(self, vehicles: int = 0, plates: int = 0, ocr: int = 0, sightings: int = 0, alerts: int = 0, routes: int = 0):
        with self._lock:
            self.total_vehicle_detections += vehicles
            self.total_plate_inferences += plates
            self.total_ocr_consensus += ocr
            self.total_sightings_persisted += sightings
            self.total_alerts_generated += alerts
            self.total_routes_computed += routes

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            uptime = time.time() - self.start_time
            latencies = list(self._request_latencies)

            p50 = p95 = p99 = mean_lat = 0.0
            if latencies:
                sorted_lat = sorted(latencies)
                n = len(sorted_lat)
                mean_lat = sum(sorted_lat) / n
                p50 = sorted_lat[int(n * 0.50)]
                p95 = sorted_lat[min(n - 1, int(n * 0.95))]
                p99 = sorted_lat[min(n - 1, int(n * 0.99))]

            # Database pool metrics
            db_metrics = {}
            try:
                import importlib
                db_m = importlib.import_module("00_foundation.registry.database")
                db_metrics = db_m.get_db_pool().get_metrics()
            except Exception:
                pass

            # Resource metrics
            rss_mb = 0.0
            cpu_percent = 0.0
            try:
                proc = psutil.Process()
                rss_mb = round(proc.memory_info().rss / (1024.0 * 1024.0), 1)
                cpu_percent = proc.cpu_percent()
            except Exception:
                pass

            vram_mb = 0.0
            if torch is not None:
                try:
                    if torch.cuda.is_available():
                        vram_mb = round(torch.cuda.memory_allocated() / (1024.0 * 1024.0), 1)
                except Exception:
                    pass


            return {
                "uptime_seconds": round(uptime, 2),
                "total_requests": self.total_requests,
                "active_requests": self.active_requests,
                "total_errors": self.total_errors,
                "latency_ms": {
                    "mean": round(mean_lat, 2),
                    "p50": round(p50, 2),
                    "p95": round(p95, 2),
                    "p99": round(p99, 2)
                },
                "active_websocket_clients": self.active_websocket_clients,
                "active_camera_workers": self.active_camera_workers,
                "total_frames_ingested": self.total_frames_ingested,
                "total_frames_dropped": self.total_frames_dropped,
                "total_frames_dropped_stale": self.total_frames_dropped_stale,
                "total_vehicle_detections": self.total_vehicle_detections,
                "total_plate_inferences": self.total_plate_inferences,
                "total_ocr_consensus": self.total_ocr_consensus,
                "total_sightings_persisted": self.total_sightings_persisted,
                "total_alerts_generated": self.total_alerts_generated,
                "total_routes_computed": self.total_routes_computed,
                "database_pool": db_metrics,
                "system": {
                    "rss_mb": rss_mb,
                    "cpu_percent": cpu_percent,
                    "vram_allocated_mb": vram_mb
                }
            }

    def to_prometheus_text(self) -> str:
        """Renders metrics in standard Prometheus exposition format."""
        s = self.snapshot()
        lines = [
            "# HELP sentineltrack_requests_total Total HTTP requests served",
            "# TYPE sentineltrack_requests_total counter",
            f"sentineltrack_requests_total {s['total_requests']}",
            "# HELP sentineltrack_errors_total Total errors encountered",
            "# TYPE sentineltrack_errors_total counter",
            f"sentineltrack_errors_total {s['total_errors']}",
            "# HELP sentineltrack_active_requests Currently active requests",
            "# TYPE sentineltrack_active_requests gauge",
            f"sentineltrack_active_requests {s['active_requests']}",
            "# HELP sentineltrack_ws_clients Active WebSocket clients",
            "# TYPE sentineltrack_ws_clients gauge",
            f"sentineltrack_ws_clients {s['active_websocket_clients']}",
            "# HELP sentineltrack_frames_ingested_total Total frames ingested",
            "# TYPE sentineltrack_frames_ingested_total counter",
            f"sentineltrack_frames_ingested_total {s['total_frames_ingested']}",
            "# HELP sentineltrack_frames_dropped_total Total frames dropped",
            "# TYPE sentineltrack_frames_dropped_total counter",
            f"sentineltrack_frames_dropped_total {s['total_frames_dropped']}",
            "# HELP sentineltrack_vehicle_detections_total Total vehicle detections",
            "# TYPE sentineltrack_vehicle_detections_total counter",
            f"sentineltrack_vehicle_detections_total {s['total_vehicle_detections']}",
            "# HELP sentineltrack_plate_inferences_total Total plate inferences",
            "# TYPE sentineltrack_plate_inferences_total counter",
            f"sentineltrack_plate_inferences_total {s['total_plate_inferences']}",
            "# HELP sentineltrack_ocr_consensus_total Total OCR track consensus results",
            "# TYPE sentineltrack_ocr_consensus_total counter",
            f"sentineltrack_ocr_consensus_total {s['total_ocr_consensus']}",
            "# HELP sentineltrack_alerts_total Total alerts generated",
            "# TYPE sentineltrack_alerts_total counter",
            f"sentineltrack_alerts_total {s['total_alerts_generated']}",
            "# HELP sentineltrack_rss_mb Process memory RSS in MB",
            "# TYPE sentineltrack_rss_mb gauge",
            f"sentineltrack_rss_mb {s['system']['rss_mb']}",
            "# HELP sentineltrack_vram_mb CUDA VRAM allocated in MB",
            "# TYPE sentineltrack_vram_mb gauge",
            f"sentineltrack_vram_mb {s['system']['vram_allocated_mb']}"
        ]
        return "\n".join(lines) + "\n"


_GLOBAL_METRICS = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    return _GLOBAL_METRICS

