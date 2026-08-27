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

    RTSPReader = reader_mod.RTSPReader
    get_camera = db_mod.get_camera
    VehicleDetector = det_mod.VehicleDetector
except Exception as e:
    print(f'[ERROR] Failed importing dependencies: {e}')
    sys.exit(1)

from pipeline import VehicleTrackingPipeline


def generate_color(track_id: int) -> tuple[int, int, int]:
    """Generates distinct consistent BGR color for each track ID."""
    np.random.seed(track_id * 31 + 7)
    color = np.random.randint(50, 255, size=3).tolist()
    return int(color[0]), int(color[1]), int(color[2])


def main():
    if len(sys.argv) < 2:
        print('Usage:')
        print('  python -m 02_tracking.scripts.test_stream <camera_id_or_url> [camera_id] [inference_interval_ms]')
        print('Examples:')
        print('  python -m 02_tracking.scripts.test_stream 1')
        print('  python -m 02_tracking.scripts.test_stream http://<HOST>:<PORT>/live/stream/1/index.m3u8 1')

        return

    arg = sys.argv[1]
    url = arg
    camera_id = sys.argv[2] if len(sys.argv) > 2 else arg
    inference_interval_ms = float(sys.argv[3]) if len(sys.argv) > 3 else 150.0

    if not (arg.startswith('rtsp://') or arg.startswith('http://') or arg.startswith('https://')):
        cam = get_camera(arg)
        if not cam:
            print(f'[ERROR] Camera ID \"{arg}\" not found in registry.')
            return
        camera_id = cam['camera_id']
        url = cam.get('hls_url') or cam.get('rtsp_url')
        if not url:
            print(f'[ERROR] No stream URL found for camera \"{camera_id}\".')
            return
        print(f'[INFO] Playing Camera {camera_id} from registry: {url}')
    else:
        print(f'[INFO] Connecting to {url} (camera_id: {camera_id})...')

    print(f'[INFO] Initializing VehicleDetector and ByteTrack pipeline for Camera {camera_id}...')
    detector = VehicleDetector(model_path='models/vehicle/yolo11m.pt', confidence=0.25, imgsz=960)
    pipeline = VehicleTrackingPipeline(detector=detector)

    reader = RTSPReader(url=url, camera_id=str(camera_id))

    last_inference_pts = None
    last_tracks = []
    fps_counter = 0
    fps_start = time.perf_counter()
    measured_fps = 0.0

    print('[INFO] Starting tracking loop. Press \"q\" in video window to exit.')

    for packet in reader.packets():
        fps_counter += 1
        elapsed = time.perf_counter() - fps_start
        if elapsed >= 1.0:
            measured_fps = fps_counter / elapsed
            fps_counter = 0
            fps_start = time.perf_counter()

        # PTS-based inference sampling
        if last_inference_pts is None or (packet.pts_ms - last_inference_pts >= inference_interval_ms) or (packet.pts_ms < last_inference_pts):
            last_inference_pts = packet.pts_ms
            last_tracks = pipeline.process(packet)

        frame = packet.frame.copy()

        # Render tracked vehicles with trails
        for track in last_tracks:
            x1, y1, x2, y2 = int(track.x1), int(track.y1), int(track.x2), int(track.y2)
            color = generate_color(track.track_id)

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Draw motion trail (points connected by lines)
            if len(track.trail) > 1:
                pts = np.array(track.trail, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], False, color, 2)

            # Label: CLASS #TRACK_ID CONF (AGE)
            label = f'{track.class_name.upper()} #{track.track_id} {track.confidence:.2f} (Age: {track.age_frames})'
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(frame, (x1, max(20, y1 - 25)), (x1 + tw + 6, max(20, y1)), color, -1)
            cv2.putText(frame, label, (x1 + 3, max(20, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # Header overlay
        header = f'[{camera_id}] PTS: {packet.pts_ms:.1f}ms | Epoch: {packet.stream_epoch} | Stream FPS: {measured_fps:.1f} | Active Tracks: {len(last_tracks)}'
        cv2.rectangle(frame, (10, 10), (880, 45), (0, 0, 0), -1)
        cv2.putText(frame, header, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

        cv2.imshow(f'Sentinel Track — ByteTrack {camera_id}', frame)
        if (cv2.waitKey(1) & 0xFF) == ord('q'):
            break

    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
