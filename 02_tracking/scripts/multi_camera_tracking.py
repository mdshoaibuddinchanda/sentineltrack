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
db_mod = importlib.import_module('00_foundation.registry.database')
det_mod = importlib.import_module('01_vehicle_detection.detector')
pipe_mod = importlib.import_module('02_tracking.pipeline')

RTSPReader = reader_mod.RTSPReader
get_camera = db_mod.get_camera
VehicleDetector = det_mod.VehicleDetector
VehicleTrackingPipeline = pipe_mod.VehicleTrackingPipeline


def run_multi_camera(camera_ids: list[str], frames_per_camera: int = 15):
    print(f'[MULTI-CAMERA] Testing independent tracking across {len(camera_ids)} cameras: {camera_ids}')

    detector = VehicleDetector(model_path='models/vehicle/yolo11m.pt', confidence=0.25, imgsz=960)
    pipeline = VehicleTrackingPipeline(detector=detector)

    for cid in camera_ids:
        cam = get_camera(cid)
        if not cam:
            print(f'[WARN] Camera {cid} not found in database.')
            continue

        url = cam.get('hls_url') or cam.get('rtsp_url')
        if not url:
            print(f'[WARN] No stream URL for camera {cid}.')
        cname = cam.get("name", "Camera")
        print(f"\n--- TESTING CAMERA {cid} ({cname}) ---")
        print(f"URL: {url}")


        reader = RTSPReader(url=url, camera_id=str(cid))
        processed = 0

        for packet in reader.packets():
            tracks = pipeline.process(packet)
            processed += 1
            print(f'[{cid}] Frame #{processed:>2} | PTS: {packet.pts_ms:>7.1f}ms | Active Tracks: {len(tracks)}')
            for t in tracks:
                print(f'   -> Track #{t.track_id:<2} {t.class_name.upper():<7} (Age: {t.age_frames} frames) @ ({t.center[0]:.0f}, {t.center[1]:.0f})')

            if processed >= frames_per_camera:
                break

    print('\n[MULTI-CAMERA TEST COMPLETE] All cameras tracked with independent isolated state.')


def main():
    cameras_to_test = sys.argv[1:] if len(sys.argv) > 1 else ['1', '2', '3']
    run_multi_camera(cameras_to_test, frames_per_camera=10)


if __name__ == '__main__':
    main()
