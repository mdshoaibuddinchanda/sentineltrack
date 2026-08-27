import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import cv2
import numpy as np
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

    PlateDetector = plate_det_mod.PlateDetector
    PlateDetectionPipeline = plate_pipe_mod.PlateDetectionPipeline
except Exception as e:
    print(f'[ERROR] Failed importing dependencies: {e}')
    sys.exit(1)



def main():
    if len(sys.argv) < 2:
        print('Usage:')
        print('  python -m 03_plate_detection.scripts.test_stream <camera_id_or_url> [camera_id] [sampling_interval_ms]')
        print('Examples:')
        print('  python -m 03_plate_detection.scripts.test_stream 1')
        print('  python -m 03_plate_detection.scripts.test_stream http://<HOST>:<PORT>/live/stream/1/index.m3u8 1')

        return

    arg = sys.argv[1]
    url = arg
    camera_id = sys.argv[2] if len(sys.argv) > 2 else arg
    sampling_interval_ms = float(sys.argv[3]) if len(sys.argv) > 3 else 150.0

    if not (arg.startswith('rtsp://') or arg.startswith('http://') or arg.startswith('https://')):
        import importlib
        res_mod = importlib.import_module('00_foundation.streams.resolver')
        cam = get_camera(arg)
        if not cam:
            print(f'[ERROR] Camera ID "{arg}" not found in registry.')
            return
        camera_id = cam['camera_id']
        url, transport = res_mod.resolve_stream(cam)
        if not url:
            print(f'[ERROR] No stream URL found for camera "{camera_id}".')
            return
        print(f'[INFO] Playing Camera {camera_id} via {transport}: {url}')
    else:
        print(f'[INFO] Connecting to {url} (camera_id: {camera_id})...')


    print(f'[INFO] Initializing Vehicle Tracker and Plate Detector for Camera {camera_id}...')
    v_detector = VehicleDetector(model_path='models/vehicle/yolo11m.pt', confidence=0.25, imgsz=960)
    v_pipeline = VehicleTrackingPipeline(detector=v_detector)

    p_detector = PlateDetector(model_path='models/plate/production/best.pt', confidence=0.20, imgsz=960)
    p_pipeline = PlateDetectionPipeline(plate_detector=p_detector)


    reader = RTSPReader(url=url, camera_id=str(camera_id))

    last_inference_pts = None
    last_tracks = []
    last_plates = []
    fps_counter = 0
    fps_start = time.perf_counter()
    measured_fps = 0.0

    print('[INFO] Starting Plate Detection stream visualizer. Press \"q\" to quit.')

    for packet in reader.packets():
        fps_counter += 1
        elapsed = time.perf_counter() - fps_start
        if elapsed >= 1.0:
            measured_fps = fps_counter / elapsed
            fps_counter = 0
            fps_start = time.perf_counter()

        # PTS-based inference sampling
        if last_inference_pts is None or (packet.pts_ms - last_inference_pts >= sampling_interval_ms) or (packet.pts_ms < last_inference_pts):
            last_inference_pts = packet.pts_ms
            last_tracks = v_pipeline.process(packet)
            last_plates = p_pipeline.process(packet, last_tracks)

        frame = packet.frame.copy()

        # Draw Vehicle Boxes (Green) + Trails
        for track in last_tracks:
            x1, y1, x2, y2 = int(track.x1), int(track.y1), int(track.x2), int(track.y2)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            v_label = f'{track.class_name.upper()} #{track.track_id} (Age: {track.age_frames})'
            cv2.putText(frame, v_label, (x1, max(20, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

        # Draw Plate Boxes (Cyan) + Quality Scores
        for plate in last_plates:
            px1, py1, px2, py2 = int(plate.x1), int(plate.y1), int(plate.x2), int(plate.y2)
            cv2.rectangle(frame, (px1, py1), (px2, py2), (255, 255, 0), 2)
            p_label = f'PLATE #{plate.track_id} Q:{plate.quality_score:.2f}'
            cv2.putText(frame, p_label, (px1, max(15, py1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 0), 2)

        # Header overlay
        header = f'[{camera_id}] PTS: {packet.pts_ms:.1f}ms | Epoch: {packet.stream_epoch} | Stream FPS: {measured_fps:.1f} | Tracks: {len(last_tracks)} | Plates: {len(last_plates)}'
        cv2.rectangle(frame, (10, 10), (950, 45), (0, 0, 0), -1)
        cv2.putText(frame, header, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

        cv2.imshow(f'Sentinel Track — Plate Detection {camera_id}', frame)
        if (cv2.waitKey(1) & 0xFF) == ord('q'):
            break

    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
