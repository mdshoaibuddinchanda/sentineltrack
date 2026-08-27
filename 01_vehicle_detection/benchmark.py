import time
import json
import numpy as np
import torch
from pathlib import Path
from dataclasses import dataclass, asdict

try:
    from .models import VehicleDetection
    from .detector import VehicleDetector
except (ImportError, ValueError):
    from models import VehicleDetection
    from detector import VehicleDetector


@dataclass
class BenchmarkResult:
    camera_id: str
    resolution: str
    device: str
    total_frames: int
    total_detections: int
    class_counts: dict
    avg_inference_ms: float
    p50_inference_ms: float
    p95_inference_ms: float
    min_inference_ms: float
    max_inference_ms: float
    fps_throughput: float
    gpu_name: str
    gpu_mem_allocated_mb: float
    gpu_mem_reserved_mb: float


class VehicleDetectionBenchmark:

    def __init__(self, detector: VehicleDetector):
        self.detector = detector
        self.latencies_ms = []
        self.class_counts = {}
        self.total_detections = 0
        self.total_frames = 0
        self.resolution = 'Unknown'

    def run_on_packets(self, packets, camera_id: str = 'benchmark_cam') -> BenchmarkResult:
        self.latencies_ms.clear()
        self.class_counts.clear()
        self.total_detections = 0
        self.total_frames = 0

        start_wall = time.perf_counter()

        for packet in packets:
            if self.resolution == 'Unknown' and hasattr(packet.frame, 'shape'):
                h, w = packet.frame.shape[:2]
                self.resolution = f'{w}x{h}'

            t0 = time.perf_counter()
            dets = self.detector.detect(packet)
            t1 = time.perf_counter()

            latency_ms = (t1 - t0) * 1000.0
            self.latencies_ms.append(latency_ms)
            self.total_frames += 1
            self.total_detections += len(dets)

            for d in dets:
                self.class_counts[d.class_name] = self.class_counts.get(d.class_name, 0) + 1

        total_wall_s = time.perf_counter() - start_wall
        fps_throughput = self.total_frames / total_wall_s if total_wall_s > 0 else 0.0

        latencies = np.array(self.latencies_ms) if self.latencies_ms else np.array([0.0])

        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'
        gpu_mem_alloc = torch.cuda.memory_allocated(0) / (1024 * 1024) if torch.cuda.is_available() else 0.0
        gpu_mem_res = torch.cuda.memory_reserved(0) / (1024 * 1024) if torch.cuda.is_available() else 0.0

        res = BenchmarkResult(
            camera_id=camera_id,
            resolution=self.resolution,
            device=str(self.detector.device or ('cuda' if torch.cuda.is_available() else 'cpu')),
            total_frames=self.total_frames,
            total_detections=self.total_detections,
            class_counts=self.class_counts,
            avg_inference_ms=float(round(float(np.mean(latencies)), 2)),
            p50_inference_ms=float(round(float(np.percentile(latencies, 50)), 2)),
            p95_inference_ms=float(round(float(np.percentile(latencies, 95)), 2)),
            min_inference_ms=float(round(float(np.min(latencies)), 2)),
            max_inference_ms=float(round(float(np.max(latencies)), 2)),
            fps_throughput=float(round(fps_throughput, 2)),
            gpu_name=gpu_name,
            gpu_mem_allocated_mb=float(round(gpu_mem_alloc, 2)),
            gpu_mem_reserved_mb=float(round(gpu_mem_res, 2)),
        )

        return res

    def save_report(self, result: BenchmarkResult, output_dir: Path = Path('reports/vehicle_detection')) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        out_path = output_dir / f'benchmark_{result.camera_id}_{timestamp}.json'

        with out_path.open('w', encoding='utf-8') as f:
            json.dump(asdict(result), f, indent=2)

        return out_path
