import os
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import importlib


def setup_dev_plate_model():
    print('[DEV SETUP] Generating development synthetic dataset and baseline model...')

    prep_mod = importlib.import_module('03_plate_detection.training.prepare_dataset')
    train_mod = importlib.import_module('03_plate_detection.training.train')

    prep_mod.prepare_dataset(300)
    train_mod.main('yolo11n.pt', 5, 2, 640)

    trained_best = ROOT_DIR / 'runs' / 'plate_detection' / 'yolo_plate_detector' / 'weights' / 'best.pt'
    if not trained_best.exists():
        trained_best = ROOT_DIR / 'runs' / 'plate_detection' / 'yolo_plate_detector' / 'weights' / 'last.pt'

    dev_path = ROOT_DIR / 'models' / 'plate' / 'dev' / 'synthetic_baseline.pt'
    dev_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(trained_best), str(dev_path))

    prod_path = ROOT_DIR / 'models' / 'plate' / 'production' / 'best.pt'
    prod_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(trained_best), str(prod_path))

    print(f'[SUCCESS] Development synthetic baseline model saved to: {dev_path}')
    print(f'[SUCCESS] Copied to production testing path: {prod_path}')


if __name__ == '__main__':
    setup_dev_plate_model()
