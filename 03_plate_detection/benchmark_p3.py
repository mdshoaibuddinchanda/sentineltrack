import json
import time
import importlib
import torch
import numpy as np
from pathlib import Path

tools_bm = importlib.import_module('tools.benchmarking')
benchmark_callable = tools_bm.benchmark_callable

plate_mod = importlib.import_module('03_plate_detection.detector')
PlateDetector = plate_mod.PlateDetector

REPORTS_P3 = Path('reports/system_optimization/p3_plate')
REPORTS_P3.mkdir(parents=True, exist_ok=True)


def run_p3_benchmarks():
    print('============================================================')
    print('BENCHMARKING P3 PLATE DETECTION (YOLO11s Optimization)')
    print('============================================================')

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f'Active Device: {device}')

    # Create dummy 480x640 vehicle crop
    dummy_crop = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    results = {}

    # 1. Precision Modes (FP32 vs FP16 at imgsz 960)
    print('\n1. Precision Benchmark (FP32 vs FP16 at imgsz 960)...')
    det_fp32 = PlateDetector(imgsz=960, device=device, half=False)
    res_fp32 = benchmark_callable('plate_yolo11s_fp32', lambda: det_fp32.detect(dummy_crop), warm_up=5, iterations=20, device=device)
    results['fp32_960'] = res_fp32.to_dict()
    print(f'  FP32: P50={res_fp32.p50_ms}ms, P95={res_fp32.p95_ms}ms, FPS={res_fp32.throughput_fps}, VRAM={res_fp32.vram_allocated_mb}MB')

    det_fp16 = PlateDetector(imgsz=960, device=device, half=True)
    res_fp16 = benchmark_callable('plate_yolo11s_fp16', lambda: det_fp16.detect(dummy_crop), warm_up=5, iterations=20, device=device)
    results['fp16_960'] = res_fp16.to_dict()
    print(f'  FP16: P50={res_fp16.p50_ms}ms, P95={res_fp16.p95_ms}ms, FPS={res_fp16.throughput_fps}, VRAM={res_fp16.vram_allocated_mb}MB')

    # 2. Batch Sweep (B1 vs B2 vs B4 vs B8 at FP16)
    print('\n2. Batch Inference Sweep (B1 vs B2 vs B4 vs B8 at FP16)...')
    for b in [1, 2, 4, 8]:
        crops = [dummy_crop] * b
        det = PlateDetector(imgsz=960, device=device, half=True)
        res = benchmark_callable(f'plate_batch_{b}_fp16', lambda: det.detect_batch(crops), warm_up=5, iterations=15, batch_size=b, device=device)
        results[f'batch_{b}'] = res.to_dict()
        print(f'  Batch {b}: P50={res.p50_ms}ms, P95={res.p95_ms}ms, Throughput={res.throughput_fps} FPS, Per-Crop P50={round(res.p50_ms / b, 2)}ms')

    out_p = REPORTS_P3 / 'plate_benchmarks.json'
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f'\nSaved P3 benchmarks to {out_p}')


if __name__ == '__main__':
    run_p3_benchmarks()
