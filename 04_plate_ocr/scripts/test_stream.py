import sys
import time
import cv2
import importlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

db_mod = importlib.import_module('00_foundation.registry.database')
fnd_res = importlib.import_module('00_foundation.streams.resolver')
fnd_reader = importlib.import_module('00_foundation.streams.reader')
p1_det = importlib.import_module('01_vehicle_detection.detector')
p2_pipe = importlib.import_module('02_tracking.pipeline')
p3_det = importlib.import_module('03_plate_detection.detector')
p3_pipe = importlib.import_module('03_plate_detection.pipeline')
p4_pipe = importlib.import_module('04_plate_ocr.pipeline')

get_camera = db_mod.get_camera
resolve_stream = fnd_res.resolve_stream
RTSPReader = fnd_reader.RTSPReader
VehicleDetector = p1_det.VehicleDetector
VehicleTrackingPipeline = p2_pipe.VehicleTrackingPipeline
PlateDetector = p3_det.PlateDetector
PlateDetectionPipeline = p3_pipe.PlateDetectionPipeline
PlateOCRPipeline = p4_pipe.PlateOCRPipeline


def test_single_stream_ocr(camera_id: str = '1', max_frames: int = 15):
    cam = get_camera(camera_id)
    if not cam:
        print(f'[ERROR] Camera {camera_id} not found in catalogue.')
        return

    url, transport = resolve_stream(cam)
    if not url:
        print(f'[ERROR] No valid stream URL for Camera {camera_id}.')
        return

    print(f'================ LIVE STREAM OCR TEST (CAMERA {camera_id}) ================')
    print(f'Location: {cam.get("name") or cam.get("location")} | Transport: {transport}')


    v_detector = VehicleDetector(model_path='models/vehicle/yolo11m.pt', confidence=0.25, imgsz=960)
    p_detector = PlateDetector(model_path='models/plate/production/best.pt', confidence=0.20, imgsz=960)
    v_pipe = VehicleTrackingPipeline(detector=v_detector, sampling_interval_ms=150.0)
    p_pipe = PlateDetectionPipeline(plate_detector=p_detector, target_crop_width=960)
    ocr_pipe = PlateOCRPipeline(default_variant='gray')

    reader = RTSPReader(url=url, camera_id=str(camera_id))
    frame_count = 0

    for packet in reader.packets():
        frame_count += 1
        tracks = v_pipe.process(packet)
        plates = p_pipe.process(packet, tracks)

        for p in plates:
            h_f, w_f = packet.frame.shape[:2]
            px1, py1 = max(0, int(p.x1)), max(0, int(p.y1))
            px2, py2 = min(w_f, int(p.x2)), min(h_f, int(p.y2))

            if (px2 - px1) >= 16 and (py2 - py1) >= 8:
                crop = packet.frame[py1:py2, px1:px2].copy()
                hyp = ocr_pipe.process_observation(p, crop)
                if hyp:
                    print(f'  [PLATE OCR] Track #{p.track_id} | Raw: \"{hyp.raw_text}\" | Norm: \"{hyp.normalized_text}\" | Conf: {hyp.ocr_confidence:.2f} | Q: {p.quality_score:.2f}')

        if frame_count >= max_frames:
            break

    print('===========================================================================')


if __name__ == '__main__':
    cid = sys.argv[1] if len(sys.argv) > 1 else '1'
    test_single_stream_ocr(cid)
