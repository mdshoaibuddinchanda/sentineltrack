import time
import os
import psutil
import torch
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Callable, Any, Optional, Dict


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    warm_up_runs: int
    mean_ms: float
    median_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    std_ms: float
    throughput_fps: float
    cpu_percent: float
    ram_mb: float
    gpu_util_percent: float = 0.0
    vram_allocated_mb: float = 0.0
    vram_reserved_mb: float = 0.0
    batch_size: int = 1
    device: str = 'cpu'
    extra_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_system_resource_snapshot() -> Dict[str, float]:
    """Captures safe current CPU, RAM, and GPU memory snapshot."""
    proc = psutil.Process()
    ram_mb = proc.memory_info().rss / (1024 * 1024)
    cpu_pct = psutil.cpu_percent(interval=None)

    vram_alloc = 0.0
    vram_res = 0.0
    if torch.cuda.is_available():
        vram_alloc = torch.cuda.memory_allocated() / (1024 * 1024)
        vram_res = torch.cuda.memory_reserved() / (1024 * 1024)

    return {
        'cpu_percent': cpu_pct,
        'ram_mb': round(ram_mb, 2),
        'vram_allocated_mb': round(vram_alloc, 2),
        'vram_reserved_mb': round(vram_res, 2)
    }


def benchmark_callable(
    name: str,
    func: Callable[[], Any],
    warm_up: int = 5,
    iterations: int = 30,
    batch_size: int = 1,
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu',
    extra_metrics: Optional[Dict[str, Any]] = None
) -> BenchmarkResult:
    """
    Executes a calibrated, reproducible benchmark across a callable function.
    Synchronizes CUDA streams to capture true execution times.
    """
    # 1. Warm-up
    for _ in range(warm_up):
        func()
        if device.startswith('cuda') and torch.cuda.is_available():
            torch.cuda.synchronize()

    # Reset resource tracking
    proc = psutil.Process()
    proc.cpu_percent(interval=None)
    if device.startswith('cuda') and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    timings = []
    t_start_total = time.perf_counter()

    for _ in range(iterations):
        t0 = time.perf_counter()
        func()
        if device.startswith('cuda') and torch.cuda.is_available():
            torch.cuda.synchronize()
        t1 = time.perf_counter()
        timings.append((t1 - t0) * 1000.0)

    t_end_total = time.perf_counter()
    total_elapsed_s = t_end_total - t_start_total

    arr = np.array(timings)
    ram_mb = proc.memory_info().rss / (1024 * 1024)
    cpu_pct = proc.cpu_percent(interval=None)

    vram_alloc = 0.0
    vram_res = 0.0
    if device.startswith('cuda') and torch.cuda.is_available():
        vram_alloc = torch.cuda.max_memory_allocated() / (1024 * 1024)
        vram_res = torch.cuda.max_memory_reserved() / (1024 * 1024)

    mean_ms = float(np.mean(arr))
    throughput_fps = (iterations * batch_size) / max(total_elapsed_s, 1e-6)

    return BenchmarkResult(
        name=name,
        iterations=iterations,
        warm_up_runs=warm_up,
        mean_ms=round(mean_ms, 3),
        median_ms=round(float(np.median(arr)), 3),
        p50_ms=round(float(np.percentile(arr, 50)), 3),
        p90_ms=round(float(np.percentile(arr, 90)), 3),
        p95_ms=round(float(np.percentile(arr, 95)), 3),
        p99_ms=round(float(np.percentile(arr, 99)), 3),
        min_ms=round(float(np.min(arr)), 3),
        max_ms=round(float(np.max(arr)), 3),
        std_ms=round(float(np.std(arr)), 3),
        throughput_fps=round(throughput_fps, 2),
        cpu_percent=round(cpu_pct, 2),
        ram_mb=round(ram_mb, 2),
        vram_allocated_mb=round(vram_alloc, 2),
        vram_reserved_mb=round(vram_res, 2),
        batch_size=batch_size,
        device=device,
        extra_metrics=extra_metrics or {}
    )
