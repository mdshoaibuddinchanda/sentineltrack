import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import importlib
reader_mod = importlib.import_module('00_foundation.streams.reader')
models_mod = importlib.import_module('00_foundation.streams.models')
RTSPReader = reader_mod.RTSPReader
FramePacket = models_mod.FramePacket

from detector import VehicleDetector
from benchmark import VehicleDetectionBenchmark


def main():
    if len(sys.argv) < 2:
        print('Usage: python -m 01_vehicle_detection.scripts.benchmark_stream <rtsp_url> [camera_id] [num_frames]')
        return

    url = sys.argv[1]
    camera_id = sys.argv[2] if len(sys.argv) > 2 else 'bench_cam'
    num_frames = int(sys.argv[3]) if len(sys.argv) > 3 else 100

    print(f'[INFO] Connecting to {url} (camera_id: {camera_id})...')
    print(f'[INFO] Target benchmark frames: {num_frames}')

    reader = RTSPReader(url=url, camera_id=camera_id)
    detector = VehicleDetector(model_path='models/vehicle/yolo11m.pt', confidence=0.25, imgsz=960)
    benchmarker = VehicleDetectionBenchmark(detector)

    def packet_generator():
        count = 0
        for packet in reader.packets():
            yield packet
            count += 1
            if count >= num_frames:
                break

    print(f'[INFO] Running benchmark on {num_frames} frames...')
    result = benchmarker.run_on_packets(packet_generator(), camera_id=camera_id)

    print('\n' + '=' * 65)
    print(f'          VEHICLE DETECTION BENCHMARK REPORT: {camera_id}')
    print('=' * 65)
    print(f'Resolution            : {result.resolution}')
    print(f'Inference Device      : {result.device} ({result.gpu_name})')
    print(f'Total Frames Evaluated: {result.total_frames}')
    print(f'Total Detections      : {result.total_detections}')
    print(f'Class Breakdown       : {result.class_counts}')
    print(f'Throughput            : {result.fps_throughput:.2f} FPS')
    print(f'Avg Inference Latency : {result.avg_inference_ms:.2f} ms')
    print(f'P50 Inference Latency : {result.p50_inference_ms:.2f} ms')
    print(f'P95 Inference Latency : {result.p95_inference_ms:.2f} ms')
    print(f'GPU VRAM Allocated    : {result.gpu_mem_allocated_mb:.1f} MB')
    print(f'GPU VRAM Reserved     : {result.gpu_mem_reserved_mb:.1f} MB')
    print('=' * 65)

    out_file = benchmarker.save_report(result)
    print(f'[SAVED] Full JSON benchmark saved to: {out_file}\n')


if __name__ == '__main__':
    main()
