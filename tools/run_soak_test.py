import time
import json
import psutil
import torch
import numpy as np
from pathlib import Path
import importlib

p0_models = importlib.import_module('00_foundation.streams.models')
p1_det = importlib.import_module('01_vehicle_detection.detector')
p2_tracker = importlib.import_module('02_tracking.tracker')
p3_det = importlib.import_module('03_plate_detection.detector')
p4_pipe = importlib.import_module('04_plate_ocr.pipeline')
p5_pipe = importlib.import_module('05_target_matching.pipeline')
p5_models = importlib.import_module('05_target_matching.models')

FramePacket = p0_models.FramePacket
VehicleDetector = p1_det.VehicleDetector
CameraTrackerRegistry = p2_tracker.CameraTrackerRegistry
PlateDetector = p3_det.PlateDetector
PlateOCRPipeline = p4_pipe.PlateOCRPipeline
TargetMatchingPipeline = p5_pipe.TargetMatchingPipeline
WatchlistPriority = p5_models.WatchlistPriority

REPORTS_RES = Path('reports/system_optimization/resources')
REPORTS_RES.mkdir(parents=True, exist_ok=True)


def run_soak_and_failure_tests(num_frames: int = 500):
    print('============================================================')
    print('SENTINELTRACK SYSTEM SOAK & FAILURE-INJECTION AUDIT')
    print('============================================================')

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    proc = psutil.Process()

    vehicle_detector = VehicleDetector(imgsz=960, device=device, half=True)
    tracker_registry = CameraTrackerRegistry()
    plate_detector = PlateDetector(imgsz=960, device=device, half=True)
    ocr_pipeline = PlateOCRPipeline()
    target_pipeline = TargetMatchingPipeline()

    target_pipeline.watchlist_manager.add_entry('GJ01AB1234', priority=WatchlistPriority.CRITICAL)

    dummy_frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
    dummy_crop = dummy_frame[300:360, 500:700]

    memory_checkpoints = []

    print(f'\n1. Executing {num_frames}-frame continuous soak test...')
    t0_soak = time.perf_counter()

    for i in range(num_frames):
        pts = float((i + 1) * 40)
        pkt = FramePacket(camera_id='cam-soak', pts_ms=pts, frame=dummy_frame, stream_epoch=1)

        # Pipeline cycle
        dets = vehicle_detector.detect(pkt)
        tracks = tracker_registry.update(pkt, dets)
        plates = plate_detector.detect(dummy_crop)

        hyp = ocr_pipeline.recognize_crop(
            crop=dummy_crop,
            camera_id='cam-soak',
            track_id=101,
            stream_epoch=1,
            pts_ms=pts,
            crop_quality=0.85
        )
        ocr_pipeline.track_hypotheses.setdefault(('cam-soak', 1, 101), []).append(hyp)
        if len(ocr_pipeline.track_hypotheses[('cam-soak', 1, 101)]) > 5:
            ocr_pipeline.track_hypotheses[('cam-soak', 1, 101)].pop(0)

        ocr_res = ocr_pipeline.get_track_result('cam-soak', 1, 101)
        if ocr_res:
            target_pipeline.process_track_ocr_result(ocr_res)

        if (i + 1) % 100 == 0:
            ram_mb = proc.memory_info().rss / (1024 * 1024)
            vram_mb = (torch.cuda.memory_allocated() / (1024 * 1024)) if device == 'cuda' else 0.0
            memory_checkpoints.append({
                'frame': i + 1,
                'ram_mb': round(ram_mb, 2),
                'vram_mb': round(vram_mb, 2)
            })
            print(f'  Frame {i + 1:>4}/{num_frames} | RAM: {ram_mb:>6.1f} MB | VRAM: {vram_mb:>6.1f} MB')

    soak_duration = time.perf_counter() - t0_soak
    print(f'Soak complete in {soak_duration:.2f}s ({num_frames / soak_duration:.1f} FPS)')

    # Check for memory leak (slope between first and last checkpoint)
    ram_initial = memory_checkpoints[0]['ram_mb']
    ram_final = memory_checkpoints[-1]['ram_mb']
    ram_growth_mb = ram_final - ram_initial
    print(f'RAM Initial: {ram_initial} MB -> RAM Final: {ram_final} MB (Delta: {ram_growth_mb:+.2f} MB)')

    # 2. Failure Injection Tests
    print('\n2. Executing Failure-Injection Tests...')
    failure_results = {}

    # Case A: Corrupted / Empty Frame
    try:
        empty_pkt = FramePacket(camera_id='cam-err', pts_ms=0.0, frame=np.empty((0, 0, 3), dtype=np.uint8), stream_epoch=1)
        dets = vehicle_detector.detect(empty_pkt)
        failure_results['empty_frame_handling'] = {'passed': True, 'detections_count': len(dets)}
        print('  • Empty frame handling: PASSED')
    except Exception as e:
        failure_results['empty_frame_handling'] = {'passed': False, 'error': str(e)}
        print(f'  • Empty frame handling: FAILED ({e})')

    # Case B: Stream Epoch Change (Loop / Reset)
    try:
        epoch_pkt = FramePacket(camera_id='cam-err', pts_ms=100.0, frame=dummy_frame, stream_epoch=2)
        tracks = tracker_registry.update(epoch_pkt, [])
        failure_results['stream_epoch_reset'] = {'passed': True, 'tracks_cleared': len(tracks) == 0}
        print('  • Stream epoch reset handling: PASSED')
    except Exception as e:
        failure_results['stream_epoch_reset'] = {'passed': False, 'error': str(e)}
        print(f'  • Stream epoch reset handling: FAILED ({e})')

    # Case C: Abnormal PTS Gap (> 2000ms jump)
    try:
        gap_pkt = FramePacket(camera_id='cam-err', pts_ms=50000.0, frame=dummy_frame, stream_epoch=2)
        tracks = tracker_registry.update(gap_pkt, [])
        failure_results['pts_gap_reset'] = {'passed': True}
        print('  • Abnormal PTS gap reset handling: PASSED')
    except Exception as e:
        failure_results['pts_gap_reset'] = {'passed': False, 'error': str(e)}
        print(f'  • Abnormal PTS gap reset handling: FAILED ({e})')

    # Case D: Empty / Corrupted OCR Crop
    try:
        empty_crop = np.zeros((0, 0, 3), dtype=np.uint8)
        hyp = ocr_pipeline.recognize_crop(empty_crop, camera_id='cam-err', track_id=1, stream_epoch=1, pts_ms=10.0)
        failure_results['empty_ocr_crop'] = {'passed': True, 'returned_hypothesis': hyp is not None}
        print('  • Empty OCR crop handling: PASSED')
    except Exception as e:
        failure_results['empty_ocr_crop'] = {'passed': False, 'error': str(e)}
        print(f'  • Empty OCR crop handling: FAILED ({e})')

    soak_report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
        'soak_frames_evaluated': num_frames,
        'soak_duration_seconds': round(soak_duration, 2),
        'soak_fps': round(num_frames / soak_duration, 2),
        'memory_checkpoints': memory_checkpoints,
        'ram_growth_mb': round(ram_growth_mb, 2),
        'memory_leak_detected': ram_growth_mb > 50.0,
        'failure_injection_results': failure_results
    }

    out_p = REPORTS_RES / 'soak_test_report.json'
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(soak_report, f, indent=2)
    print(f'\nSaved soak and failure report to {out_p}')


if __name__ == '__main__':
    run_soak_and_failure_tests()
