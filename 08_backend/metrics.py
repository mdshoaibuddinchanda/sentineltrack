import time
import threading
from typing import Dict, Any


class MetricsCollector:
    """Thread-safe operational metrics collector for SentinelTrack backend."""

    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.total_requests = 0
        self.total_errors = 0
        self.active_websocket_clients = 0
        self.active_camera_workers = 0
        self.total_frames_ingested = 0
        self.total_frames_dropped = 0
        self.total_vehicle_detections = 0
        self.total_plate_inferences = 0
        self.total_ocr_consensus = 0
        self.total_sightings_persisted = 0
        self.total_alerts_generated = 0
        self.total_routes_computed = 0

    def inc_requests(self):
        with self._lock:
            self.total_requests += 1

    def inc_errors(self):
        with self._lock:
            self.total_errors += 1

    def set_ws_clients(self, count: int):
        with self._lock:
            self.active_websocket_clients = count

    def set_camera_workers(self, count: int):
        with self._lock:
            self.active_camera_workers = count

    def inc_frames(self, ingested: int = 1, dropped: int = 0):
        with self._lock:
            self.total_frames_ingested += ingested
            self.total_frames_dropped += dropped

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
            return {
                "uptime_seconds": round(uptime, 2),
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "active_websocket_clients": self.active_websocket_clients,
                "active_camera_workers": self.active_camera_workers,
                "total_frames_ingested": self.total_frames_ingested,
                "total_frames_dropped": self.total_frames_dropped,
                "total_vehicle_detections": self.total_vehicle_detections,
                "total_plate_inferences": self.total_plate_inferences,
                "total_ocr_consensus": self.total_ocr_consensus,
                "total_sightings_persisted": self.total_sightings_persisted,
                "total_alerts_generated": self.total_alerts_generated,
                "total_routes_computed": self.total_routes_computed
            }


_GLOBAL_METRICS = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    return _GLOBAL_METRICS
