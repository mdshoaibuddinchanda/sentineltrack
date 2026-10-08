import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import cv2
import importlib

det_mod = importlib.import_module('01_vehicle_detection.detector')
models_mod = importlib.import_module('00_foundation.streams.models')
track_models = importlib.import_module('02_tracking.models')

VehicleDetector = det_mod.VehicleDetector
FramePacket = models_mod.FramePacket
VehicleTrack = track_models.VehicleTrack

plate_det_mod = importlib.import_module('03_plate_detection.detector')
plate_pipe_mod = importlib.import_module('03_plate_detection.pipeline')

PlateDetector = plate_det_mod.PlateDetector
PlateDetectionPipeline = plate_pipe_mod.PlateDetectionPipeline



def main():
    img_path = sys.argv[1] if len(sys.argv) > 1 else 'reports/vehicle_detection/test_image_result.jpg'
    img = cv2.imread(img_path)
    if img is None:
        print(f'[ERROR] Could not open image: {img_path}')
        return

    print(f'[INFO] Processing image: {img_path} ({img.shape[1]}x{img.shape[0]})')

    # Run vehicle detector
    v_detector = VehicleDetector(model_path='models/vehicle/yolo11m.pt', confidence=0.25)
    packet = FramePacket(camera_id='img_test', pts_ms=0.0, frame=img, stream_epoch=0)
    v_dets = v_detector.detect(packet)

    print(f'[INFO] Detected {len(v_dets)} vehicles.')

    # Convert to mock tracks
    tracks = []
    for i, d in enumerate(v_dets):
        tracks.append(VehicleTrack(
            camera_id='img_test',
            track_id=i + 1,
            stream_epoch=0,
            first_pts_ms=0.0,
            last_pts_ms=0.0,
            class_id=d.class_id,
            class_name=d.class_name,
            confidence=d.confidence,
            x1=d.x1, y1=d.y1, x2=d.x2, y2=d.y2,
        ))

    # Run plate detection pipeline with dedicated single-class plate detector
    p_detector = PlateDetector(model_path='models/plate/yolo11s_plate_v2.pt', confidence=0.20, imgsz=960)
    pipeline = PlateDetectionPipeline(plate_detector=p_detector)


    plates = pipeline.process(packet, tracks)
    print(f'[INFO] Detected {len(plates)} license plates across {len(tracks)} vehicles.')

    out_img = img.copy()

    # Draw vehicles (Green)
    for t in tracks:
        cv2.rectangle(out_img, (int(t.x1), int(t.y1)), (int(t.x2), int(t.y2)), (0, 255, 0), 2)
        cv2.putText(out_img, f'{t.class_name.upper()} #{t.track_id}', (int(t.x1), max(20, int(t.y1) - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # Draw plates (Yellow/Cyan)
    for p in plates:
        cv2.rectangle(out_img, (int(p.x1), int(p.y1)), (int(p.x2), int(p.y2)), (0, 255, 255), 2)
        label = f'PLATE {p.confidence:.2f} (Q:{p.quality_score:.2f})'
        cv2.putText(out_img, label, (int(p.x1), max(15, int(p.y1) - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 2)

    out_path = Path('reports/plate_detection/successful/test_image_plates.jpg')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), out_img)
    print(f'[SUCCESS] Annotated result saved to: {out_path}')


if __name__ == '__main__':
    main()
