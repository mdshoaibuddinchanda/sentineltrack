import sys
from pathlib import Path

# Add project root and 01_vehicle_detection to sys.path
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
    models_mod = importlib.import_module("00_foundation.streams.models")
    FramePacket = models_mod.FramePacket
except Exception:
    from dataclasses import dataclass
    @dataclass
    class FramePacket:
        camera_id: str
        pts_ms: float
        frame: np.ndarray
        stream_epoch: int = 0


from detector import VehicleDetector, VEHICLE_CLASSES


def create_synthetic_street_image() -> np.ndarray:
    """Creates a sample test canvas if no image path is passed."""
    img = np.full((720, 1280, 3), 40, dtype=np.uint8)
    # Draw simple road
    cv2.rectangle(img, (0, 300), (1280, 720), (70, 70, 70), -1)
    cv2.line(img, (0, 510), (1280, 510), (255, 255, 255), 4)
    cv2.putText(img, 'Sentinel Vehicle Detection Test Canvas', (50, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (200, 200, 200), 2)
    return img


def main():
    image_path = sys.argv[1] if len(sys.argv) > 1 else None

    if image_path and Path(image_path).exists():
        frame = cv2.imread(str(image_path))
        print(f'[INFO] Loaded input image: {image_path} ({frame.shape[1]}x{frame.shape[0]})')
    else:
        print('[INFO] No image provided or file not found. Generating test canvas...')
        frame = create_synthetic_street_image()

    packet = FramePacket(
        camera_id='test_cam_01',
        pts_ms=0.0,
        frame=frame,
        stream_epoch=0,
    )

    print('[INFO] Initializing VehicleDetector (yolo11m.pt)...')
    detector = VehicleDetector(model_path='models/vehicle/yolo11m.pt', confidence=0.25, imgsz=960)

    print('[INFO] Running inference...')
    detections = detector.detect(packet)

    print(f"\n[RESULTS] Detected {len(detections)} vehicles:")
    print(f"{'Class':<15} | {'Confidence':<10} | {'Bounding Box (x1, y1, x2, y2)'}")
    print("-" * 60)


    for det in detections:
        print(f'{det.class_name:<15} | {det.confidence:<10.2f} | ({det.x1:.1f}, {det.y1:.1f}, {det.x2:.1f}, {det.y2:.1f})')

        # Draw bbox
        cv2.rectangle(frame, (int(det.x1), int(det.y1)), (int(det.x2), int(det.y2)), (0, 255, 0), 2)
        label = f'{det.class_name} {det.confidence:.2f}'
        cv2.putText(frame, label, (int(det.x1), max(20, int(det.y1) - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    out_dir = Path('reports/vehicle_detection')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / 'test_image_result.jpg'
    cv2.imwrite(str(out_file), frame)
    print(f'\n[SAVED] Annotated image saved to: {out_file}')


if __name__ == '__main__':
    main()
