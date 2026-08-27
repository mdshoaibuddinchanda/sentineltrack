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

try:
    from 00_foundation.streams.reader import RTSPReader
    from 00_foundation.streams.models import FramePacket
except Exception:
    import importlib
    reader_mod = importlib.import_module('00_foundation.streams.reader')
    models_mod = importlib.import_module('00_foundation.streams.models')
    RTSPReader = reader_mod.RTSPReader
    FramePacket = models_mod.FramePacket

from detector import VehicleDetector


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m 01_vehicle_detection.scripts.test_stream <camera_id_or_url> [camera_id] [inference_interval_ms]")
        print("Examples:")
        print("  python -m 01_vehicle_detection.scripts.test_stream 1")
        print("  python -m 01_vehicle_detection.scripts.test_stream http://<HOST>:<PORT>/live/stream/1/index.m3u8 1 150")

        return

    arg = sys.argv[1]
    url = arg
    camera_id = sys.argv[2] if len(sys.argv) > 2 else arg
    inference_interval_ms = float(sys.argv[3]) if len(sys.argv) > 3 else 150.0

    if not (arg.startswith("rtsp://") or arg.startswith("http://") or arg.startswith("https://")):
        import importlib
        db_mod = importlib.import_module("00_foundation.registry.database")
        cam = db_mod.get_camera(arg)
        if not cam:
            print(f"[ERROR] Camera ID '{arg}' not found in registry.")
            return
        camera_id = cam["camera_id"]
        url = cam.get("hls_url") or cam.get("rtsp_url")
        if not url:
            print(f"[ERROR] No stream URL found for camera '{camera_id}'.")
            return
        print(f"[INFO] Playing Camera {camera_id} from registry: {url}")
    else:
        print(f"[INFO] Connecting to {url} (camera_id: {camera_id})...")

    print(f"[INFO] PTS inference sampling interval: {inference_interval_ms} ms (~{1000/inference_interval_ms:.1f} FPS)")

    reader = RTSPReader(url=url, camera_id=str(camera_id))
    detector = VehicleDetector(model_path="models/vehicle/yolo11m.pt", confidence=0.25, imgsz=960)


    last_inference_pts = None
    last_detections = []
    fps_counter = 0
    fps_start = time.perf_counter()
    measured_fps = 0.0

    for packet in reader.packets():
        fps_counter += 1
        elapsed = time.perf_counter() - fps_start
        if elapsed >= 1.0:
            measured_fps = fps_counter / elapsed
            fps_counter = 0
            fps_start = time.perf_counter()

        # Step 8: PTS-based sampling
        if last_inference_pts is None or (packet.pts_ms - last_inference_pts >= inference_interval_ms) or (packet.pts_ms < last_inference_pts):
            last_inference_pts = packet.pts_ms
            last_detections = detector.detect(packet)

        frame = packet.frame.copy()

        # Render bounding boxes
        for det in last_detections:
            x1, y1, x2, y2 = int(det.x1), int(det.y1), int(det.x2), int(det.y2)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f'{det.class_name} {det.confidence:.2f}'
            cv2.putText(frame, label, (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

        # Header overlay
        header = f'[{camera_id}] PTS: {packet.pts_ms:.1f}ms | Epoch: {packet.stream_epoch} | Stream FPS: {measured_fps:.1f} | Dets: {len(last_detections)}'
        cv2.rectangle(frame, (10, 10), (850, 45), (0, 0, 0), -1)
        cv2.putText(frame, header, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

        cv2.imshow(f'Sentinel Track — {camera_id}', frame)
        if (cv2.waitKey(1) & 0xFF) == ord('q'):
            break

    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
