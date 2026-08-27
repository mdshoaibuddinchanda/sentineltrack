import sys
import time
import json
from pathlib import Path
from dataclasses import dataclass, asdict

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import torch


@dataclass
class PlateBenchmarkResult:
    model_path: str
    device: str
    target_crop_width: int
    num_crops_processed: int
    num_plates_detected: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    fps_throughput: float
    gpu_memory_allocated_mb: float


class PlateDetectionBenchmark:
    def __init__(self, detector, target_crop_width: int = 960):
        self.detector = detector
        self.target_crop_width = target_crop_width

    def run(self, sample_crops: list[np.ndarray]) -> PlateBenchmarkResult:
        latencies = []
        num_detected = 0

        # Warmup
        if sample_crops:
            for _ in range(3):
                self.detector.detect(sample_crops[0])

        for crop in sample_crops:
            t0 = time.perf_counter()
            plates = self.detector.detect(crop)
            t1 = time.perf_counter()

            latencies.append((t1 - t0) * 1000.0)
            num_detected += len(plates)

        avg_lat = float(np.mean(latencies)) if latencies else 0.0
        p50_lat = float(np.median(latencies)) if latencies else 0.0
        p95_lat = float(np.percentile(latencies, 95)) if latencies else 0.0
        fps = 1000.0 / avg_lat if avg_lat > 0 else 0.0

        vram = 0.0
        if torch.cuda.is_available():
            vram = torch.cuda.memory_allocated() / (1024 * 1024)

        return PlateBenchmarkResult(
            model_path=self.detector.model_path,
            device=self.detector.device,
            target_crop_width=self.target_crop_width,
            num_crops_processed=len(sample_crops),
            num_plates_detected=num_detected,
            avg_latency_ms=round(avg_lat, 2),
            p50_latency_ms=round(p50_lat, 2),
            p95_latency_ms=round(p95_lat, 2),
            fps_throughput=round(fps, 1),
            gpu_memory_allocated_mb=round(vram, 2),
        )
