import sys
import time
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import importlib
try:
    reader_mod = importlib.import_module('00_foundation.streams.reader')
    db_mod = importlib.import_module('00_foundation.registry.database')
    det_mod = importlib.import_module('01_vehicle_detection.detector')
    track_pipe_mod = importlib.import_module('02_tracking.pipeline')

    RTSPReader = reader_mod.RTSPReader
    get_camera = db_mod.get_camera
    VehicleDetector = det_mod.VehicleDetector
    VehicleTrackingPipeline = track_pipe_mod.VehicleTrackingPipeline
    plate_det_mod = importlib.import_module('03_plate_detection.detector')
    plate_pipe_mod = importlib.import_module('03_plate_detection.pipeline')
    bench_mod = importlib.import_module('03_plate_detection.benchmark')

    PlateDetector = plate_det_mod.PlateDetector
    PlateDetectionPipeline = plate_pipe_mod.PlateDetectionPipeline
    PlateDetectionBenchmark = bench_mod.PlateDetectionBenchmark
except Exception as e:
    print(f'[ERROR] Dependencies error: {e}')
    sys.exit(1)



def main():
    target = sys.argv[1] if len(sys.argv) > 1 else '1'
    max_frames = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    url = target
    camera_id = target
    if not (target.startswith('rtsp://') or target.startswith('http://') or target.startswith('https://')):
        import importlib
        res_mod = importlib.import_module('00_foundation.streams.resolver')
        cam = get_camera(target)
        if not cam:
            print(f'[ERROR] Camera {target} not found.')
            return
        camera_id = cam['camera_id']
        url, transport = res_mod.resolve_stream(cam)
        if not url:
            print(f'[ERROR] No stream URL for {target}.')
            return

    print(f'[BENCHMARK] Starting Plate Detection Benchmark on {camera_id} ({url}) for {max_frames} frames...')


    v_detector = VehicleDetector(model_path='models/vehicle/yolo11m.pt', confidence=0.25, imgsz=960)
    v_pipeline = VehicleTrackingPipeline(detector=v_detector)

    p_detector = PlateDetector(model_path='models/plate/yolo11s_plate_v2.pt', confidence=0.20, imgsz=960)
    p_pipeline = PlateDetectionPipeline(plate_detector=p_detector)


    reader = RTSPReader(url=url, camera_id=str(camera_id))

    crops_collected = []
    frames_processed = 0
    total_plates = 0

    t_start = time.perf_counter()

    for packet in reader.packets():
        tracks = v_pipeline.process(packet)
        plates = p_pipeline.process(packet, tracks)
        total_plates += len(plates)
        frames_processed += 1
        if frames_processed >= max_frames:
            break

    total_time = time.perf_counter() - t_start
    overall_fps = frames_processed / total_time if total_time > 0 else 0.0

    report = {
        'camera_id': camera_id,
        'frames_evaluated': frames_processed,
        'total_plates_detected': total_plates,
        'total_elapsed_seconds': round(total_time, 2),
        'end_to_end_pipeline_fps': round(overall_fps, 2),
        'device': p_detector.device,
        'plate_model': p_detector.model_path,
    }

    out_dir = Path('reports/plate_detection')
    ts_str = time.strftime("%Y%m%d_%H%M%S")
    report_file = out_dir / f"plate_benchmark_{camera_id}_{ts_str}.json"


    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    print(f'\n=== PLATE DETECTION BENCHMARK RESULTS ===')
    print(f'Camera: {camera_id}')
    print(f'Frames Processed: {frames_processed}')
    print(f'Plates Detected: {total_plates}')
    print(f'Throughput: {overall_fps:.1f} FPS')
    print(f'Report Saved: {report_file}')


if __name__ == '__main__':
    main()
