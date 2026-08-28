import time
import math
from typing import Dict, List, Optional, Any
from collections import defaultdict

try:
    import torch
except ImportError:
    torch = None



class StageMetrics:
    def __init__(self, name: str):
        self.name = name
        self.latencies_ms: List[float] = []

    def record(self, duration_ms: float) -> None:
        self.latencies_ms.append(duration_ms)

    def compute_stats(self) -> Dict[str, Any]:
        if not self.latencies_ms:
            return {
                "count": 0,
                "mean_ms": 0.0,
                "min_ms": 0.0,
                "p50_ms": 0.0,
                "p90_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "max_ms": 0.0,
                "throughput_fps": 0.0
            }

        sorted_lat = sorted(self.latencies_ms)
        n = len(sorted_lat)

        def percentile(p: float) -> float:
            k = (n - 1) * p
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return sorted_lat[int(k)]
            d0 = sorted_lat[int(f)] * (c - k)
            d1 = sorted_lat[int(c)] * (k - f)
            return d0 + d1

        mean_val = sum(sorted_lat) / n
        fps = (1000.0 / mean_val) if mean_val > 0 else 0.0

        return {
            "count": n,
            "mean_ms": round(mean_val, 2),
            "min_ms": round(sorted_lat[0], 2),
            "p50_ms": round(percentile(0.50), 2),
            "p90_ms": round(percentile(0.90), 2),
            "p95_ms": round(percentile(0.95), 2),
            "p99_ms": round(percentile(0.99), 2),
            "max_ms": round(sorted_lat[-1], 2),
            "throughput_fps": round(fps, 2)
        }


class PipelineProfiler:
    """
    High-precision pipeline profiler with CUDA-synchronized timing,
    warmup exclusion, and stage-by-stage latency distributions.
    """

    def __init__(self, warmup_iterations: int = 5):
        self.warmup_iterations = warmup_iterations
        self._iteration_count = 0
        self._stages: Dict[str, StageMetrics] = defaultdict(lambda: StageMetrics("unknown"))
        self._is_cuda = bool(torch and torch.cuda.is_available())


    def stage_timer(self, stage_name: str):
        """Context manager for timing a stage with CUDA synchronization."""
        return _StageTimerContext(self, stage_name)

    def record_stage(self, stage_name: str, duration_ms: float) -> None:
        """Records a stage duration if past warmup iterations."""
        if self._iteration_count >= self.warmup_iterations:
            if stage_name not in self._stages:
                self._stages[stage_name] = StageMetrics(stage_name)
            self._stages[stage_name].record(duration_ms)

    def mark_iteration(self) -> None:
        """Marks the completion of one end-to-end processing iteration."""
        self._iteration_count += 1

    def get_report(self) -> Dict[str, Any]:
        """Generates a complete latency and throughput profile across all stages."""
        report = {
            "warmup_iterations": self.warmup_iterations,
            "profiled_iterations": max(0, self._iteration_count - self.warmup_iterations),
            "stages": {}
        }
        for name, stage in self._stages.items():
            report["stages"][name] = stage.compute_stats()
        return report


class _StageTimerContext:
    def __init__(self, profiler: PipelineProfiler, stage_name: str):
        self.profiler = profiler
        self.stage_name = stage_name
        self.start_time = 0.0

    def __enter__(self):
        if self.profiler._is_cuda:
            try:
                torch.cuda.synchronize()
            except Exception:
                pass
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.profiler._is_cuda:
            try:
                torch.cuda.synchronize()
            except Exception:
                pass
        elapsed_ms = (time.perf_counter() - self.start_time) * 1000.0
        self.profiler.record_stage(self.stage_name, elapsed_ms)
