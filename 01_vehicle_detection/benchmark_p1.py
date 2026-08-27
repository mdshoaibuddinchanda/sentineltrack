import json
import time
import cv2
import importlib
import torch
import numpy as np
from pathlib import Path

tools_bm = importlib.import_module('tools.benchmarking')
benchmark_callable = tools_bm.benchmark_callable

det_mod = importlib.import_module('01_vehicle_detection.detector')
p0_models = importlib.import_module('00_foundation.streams.models')

VehicleDetector = det_mod.VehicleDetector
FramePacket = p0_models.FramePacket

REPORTS_P1 = Path('reports/system_optimization/p1_vehicle')
REPORTS_P1.mkdir(parents=True, exist_ok=True)


def run_p1_benchmarks():
    print('============================================================')
    print('BENCHMARKING P1 VEHICLE DETECTION (YOLO11m Optimization)')
    print('============================================================')

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f'Active Device: {device}')

    # Create dummy 1080p frame
    dummy_frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
    dummy_packet = FramePacket(camera_id='cam-bench-p1', pts_ms=100.0, frame=dummy_frame, stream_epoch=1)

    results = {}

    # 1. Precision Modes (FP32 vs FP16 at imgsz 960)
    print('\n1. Precision Benchmark (FP32 vs FP16 at imgsz 960)...')
    det_fp32 = VehicleDetector(imgsz=960, device=device, half=False)
    res_fp32 = benchmark_callable('yolo11m_960_fp32', lambda: det_fp32.detect(dummy_packet), warm_up=5, iterations=20, device=device)
    results['fp32_960'] = res_fp32.to_dict()
    print(f'  FP32: P50={res_fp32.p50_ms}ms, P95={res_fp32.p95_ms}ms, FPS={res_fp32.throughput_fps}, VRAM={res_fp32.vram_allocated_mb}MB')

    det_fp16 = VehicleDetector(imgsz=960, device=device, half=True)
    res_fp16 = benchmark_callable('yolo11m_960_fp16', lambda: det_fp16.detect(dummy_packet), warm_up=5, iterations=20, device=device)
    results['fp16_960'] = res_fp16.to_dict()
    print(f'  FP16: P50={res_fp16.p50_ms}ms, P95={res_fp16.p95_ms}ms, FPS={res_fp16.throughput_fps}, VRAM={res_fp16.vram_allocated_mb}MB')

    # 2. Resolution Sweep (640 vs 768 vs 960 at FP16)
    print('\n2. Resolution Sweep (640 vs 768 vs 960 at FP16)...')
    for sz in [640, 768, 960]:
        det = VehicleDetector(imgsz=sz, device=device, half=True)
        res = benchmark_callable(f'yolo11m_{sz}_fp16', lambda: det.detect(dummy_packet), warm_up=5, iterations=20, device=device)
        results[f'res_{sz}'] = res.to_dict()
        print(f'  imgsz {sz}: P50={res.p50_ms}ms, P95={res.p95_ms}ms, FPS={res.throughput_fps}, VRAM={res.vram_allocated_mb}MB')

    # 3. Batch Sweep (B1 vs B2 vs B4 at imgsz 960 FP16)
    print('\n3. Batch Inference Sweep (B1 vs B2 vs B4 at imgsz 960 FP16)...')
    for b in [1, 2, 4]:
        packets = [dummy_packet] * b
        det = VehicleDetector(imgsz=960, device=device, half=True)
        res = benchmark_callable(f'yolo11m_batch_{b}_fp16', lambda: det.detect_batch(packets), warm_up=5, iterations=15, batch_size=b, device=device)
        results[f'batch_{b}'] = res.to_dict()
        print(f'  Batch {b}: P50={res.p50_ms}ms, P95={res.p95_ms}ms, Throughput={res.throughput_fps} FPS, Per-Frame P50={round(res.p50_ms / b, 2)}ms')

    out_p = REPORTS_P1 / 'vehicle_benchmarks.json'
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f'\nSaved P1 benchmarks to {out_p}')


if __name__ == '__main__':
    run_p1_benchmarks()
