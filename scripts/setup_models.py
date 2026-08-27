import os
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ultralytics import YOLO


def setup_models():
    print('[SETUP] Setting up AI models for SentinelTrack...')

    # 1. Vehicle Detection Model (yolo11m.pt)
    vehicle_dir = ROOT_DIR / 'models' / 'vehicle'
    vehicle_dir.mkdir(parents=True, exist_ok=True)
    vehicle_model_path = vehicle_dir / 'yolo11m.pt'

    if not vehicle_model_path.exists():
        print('[SETUP] Downloading YOLO11m vehicle detection model...')
        v_model = YOLO('yolo11m.pt')
        if Path('yolo11m.pt').exists():
            shutil.copy2('yolo11m.pt', str(vehicle_model_path))
    else:
        print(f'[SETUP] Vehicle detector exists at: {vehicle_model_path}')

    # 2. Dedicated Single-Class License Plate Model (best.pt)
    plate_model_path_str = os.getenv('PLATE_MODEL_PATH', 'models/plate/production/best.pt')
    plate_model_path = Path(plate_model_path_str)
    if not plate_model_path.is_absolute():
        plate_model_path = ROOT_DIR / plate_model_path

    if not plate_model_path.exists():
        raise FileNotFoundError(
            f"\n[ERROR] Production license-plate model not found at '{plate_model_path}'.\n"
            f"To generate a development synthetic baseline model, run:\n"
            f"  python scripts/setup_dev_plate_model.py\n"
            f"Or specify a trained model path using the PLATE_MODEL_PATH environment variable."
        )
    else:
        print(f'[SETUP] Validated plate detector found at: {plate_model_path}')

    # 3. Verify Model Contracts
    print('\n[SETUP] Verifying model contracts:')
    v_loaded = YOLO(str(vehicle_model_path))
    print(f'  - Vehicle model classes: {len(v_loaded.names)} classes loaded')

    p_loaded = YOLO(str(plate_model_path))
    print(f'  - Plate model classes: {p_loaded.names}')
    assert len(p_loaded.names) == 1 and p_loaded.names[0] == 'license_plate', 'Plate model failed single-class contract!'

    print('\n[SUCCESS] All SentinelTrack models are verified and ready.')


if __name__ == '__main__':
    setup_models()

