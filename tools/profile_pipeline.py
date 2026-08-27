import time
import json
import importlib
import torch
import numpy as np
from pathlib import Path

tools_bm = importlib.import_module('tools.benchmarking')
get_system_resource_snapshot = tools_bm.get_system_resource_snapshot

p0_models = importlib.import_module('00_foundation.streams.models')
p1_det = importlib.import_module('01_vehicle_detection.detector')
p2_tracker = importlib.import_module('02_tracking.tracker')
p3_cropper = importlib.import_module('03_plate_detection.cropper')
p3_det = importlib.import_module('03_plate_detection.detector')
p4_pipe = importlib.import_module('04_plate_ocr.pipeline')
p5_pipe = importlib.import_module('05_target_matching.pipeline')
p5_models = importlib.import_module('05_target_matching.models')

FramePacket = p0_models.FramePacket
VehicleDetector = p1_det.VehicleDetector
CameraTrackerRegistry = p2_tracker.CameraTrackerRegistry
crop_vehicle = p3_cropper.crop_vehicle
PlateDetector = p3_det.PlateDetector
PlateOCRPipeline = p4_pipe.PlateOCRPipeline
TargetMatchingPipeline = p5_pipe.TargetMatchingPipeline
WatchlistPriority = p5_models.WatchlistPriority

REPORTS_E2E = Path('reports/system_optimization/end_to_end')
REPORTS_E2E.mkdir(parents=True, exist_ok=True)


def profile_end_to_end_pipeline(iterations: int = 25):
    print('============================================================')
    print('PROFILING SENTINELTRACK COMPLETE PIPELINE (P0 -> P5)')
    print('============================================================')

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f'Active Device: {device}')

    # 1. Initialize Subsystems
    vehicle_detector = VehicleDetector(imgsz=960, device=device, half=True)
    tracker_registry = CameraTrackerRegistry()
    plate_detector = PlateDetector(imgsz=960, device=device, half=True)
    ocr_pipeline = PlateOCRPipeline()
    target_pipeline = TargetMatchingPipeline()

    # Pre-register targets on Watchlist
    target_pipeline.watchlist_manager.add_entry('GJ01AB1234', priority=WatchlistPriority.CRITICAL)
    target_pipeline.watchlist_manager.add_entry('MH12DE1432', priority=WatchlistPriority.HIGH)
    target_pipeline.watchlist_manager.add_entry('DL01AB9999', priority=WatchlistPriority.NORMAL)

    # Synthetic realistic frame (1920x1080)
    dummy_frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)

    stage_timings = {
        'p1_vehicle_detection': [],
        'p2_tracking': [],
        'p3_vehicle_crop': [],
        'p3_plate_detection': [],
        'p4_ocr_and_voting': [],
        'p5_target_matching_and_persistence': [],
        'total_pipeline_frame_latency': []
    }

    # Warm-up (3 cycles)
    for _ in range(3):
        pkt = FramePacket(camera_id='cam-e2e', pts_ms=100.0, frame=dummy_frame, stream_epoch=1)
        dets = vehicle_detector.detect(pkt)
        tracks = tracker_registry.update(pkt, dets)

    print(f'\nRunning {iterations} end-to-end profile iterations...')

    for i in range(iterations):
        pts = float((i + 1) * 40)
        pkt = FramePacket(camera_id='cam-e2e', pts_ms=pts, frame=dummy_frame, stream_epoch=1)

        t_start = time.perf_counter()

        # P1: Vehicle Detection
        t0 = time.perf_counter()
        dets = vehicle_detector.detect(pkt)
        if device == 'cuda':
            torch.cuda.synchronize()
        t1 = time.perf_counter()
        stage_timings['p1_vehicle_detection'].append((t1 - t0) * 1000.0)

        # P2: Tracking
        t0 = time.perf_counter()
        tracks = tracker_registry.update(pkt, dets)
        t1 = time.perf_counter()
        stage_timings['p2_tracking'].append((t1 - t0) * 1000.0)

        # P3: Vehicle Cropping & Plate Detection
        t0 = time.perf_counter()
        # Simulate vehicle crop for detected track
        v_crop = dummy_frame[200:600, 400:1000]
        t1 = time.perf_counter()
        stage_timings['p3_vehicle_crop'].append((t1 - t0) * 1000.0)

        t0 = time.perf_counter()
        plates = plate_detector.detect(v_crop)
        if device == 'cuda':
            torch.cuda.synchronize()
        t1 = time.perf_counter()
        stage_timings['p3_plate_detection'].append((t1 - t0) * 1000.0)

        # P4: OCR & Voting
        t0 = time.perf_counter()
        p_crop = dummy_frame[300:360, 500:700]
        hyp = ocr_pipeline.recognize_crop(
            crop=p_crop,
            camera_id='cam-e2e',
            track_id=101,
            stream_epoch=1,
            pts_ms=pts,
            crop_quality=0.88
        )
        ocr_pipeline.track_hypotheses.setdefault(('cam-e2e', 1, 101), []).append(hyp)
        ocr_res = ocr_pipeline.get_track_result('cam-e2e', 1, 101)
        t1 = time.perf_counter()
        stage_timings['p4_ocr_and_voting'].append((t1 - t0) * 1000.0)

        # P5: Target Matching & Persistence
        t0 = time.perf_counter()
        if ocr_res is not None:
            cands, alerts, sighting = target_pipeline.process_track_ocr_result(ocr_res)
        t1 = time.perf_counter()
        stage_timings['p5_target_matching_and_persistence'].append((t1 - t0) * 1000.0)

        t_end = time.perf_counter()
        stage_timings['total_pipeline_frame_latency'].append((t_end - t_start) * 1000.0)

    # Compute Statistics
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
        'iterations': iterations,
        'device': device,
        'resources': get_system_resource_snapshot(),
        'stages': {}
    }

    print('\n------------------------------------------------------------')
    print('STAGE TIMING BREAKDOWN (P0 -> P5):')
    for stage_name, times in stage_timings.items():
        arr = np.array(times)
        p50 = float(np.percentile(arr, 50))
        p95 = float(np.percentile(arr, 95))
        mean = float(np.mean(arr))
        report['stages'][stage_name] = {
            'mean_ms': round(mean, 2),
            'p50_ms': round(p50, 2),
            'p95_ms': round(p95, 2),
            'min_ms': round(float(np.min(arr)), 2),
            'max_ms': round(float(np.max(arr)), 2)
        }
        print(f'  {stage_name:<36}: P50={p50:>6.2f} ms | P95={p95:>6.2f} ms | Mean={mean:>6.2f} ms')
    print('------------------------------------------------------------')

    out_p = REPORTS_E2E / 'pipeline_profile.json'
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(f'Saved pipeline profile to {out_p}')


if __name__ == '__main__':
    profile_end_to_end_pipeline()
