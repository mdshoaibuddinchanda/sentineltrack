import os
import shutil
import sys
from pathlib import Path
from ultralytics import YOLO

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else 'yolo11s.pt'
    epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    batch_size = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    imgsz = int(sys.argv[4]) if len(sys.argv) > 4 else 640

    print(f'[TRAIN] Initializing single-class license plate training with base {model_name} (batch={batch_size}, imgsz={imgsz})...')
    model = YOLO(model_name)

    dataset_yaml = ROOT_DIR / '03_plate_detection' / 'training' / 'dataset.yaml'

    model.train(
        data=str(dataset_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        device=0,
        patience=15,
        workers=0,
        plots=False,
        project='runs/plate_detection',
        name='yolo_plate_detector',
        exist_ok=True,
    )


    trained_best = Path('runs/plate_detection/yolo_plate_detector/weights/best.pt')
    if not trained_best.exists():
        trained_best = Path('runs/plate_detection/yolo_plate_detector/weights/last.pt')

    prod_path = ROOT_DIR / 'models' / 'plate' / 'production' / 'best.pt'
    base_path = ROOT_DIR / 'models' / 'plate' / 'baseline' / 'best.pt'
    prod_path.parent.mkdir(parents=True, exist_ok=True)
    base_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(str(trained_best), str(prod_path))
    shutil.copy2(str(trained_best), str(base_path))

    print(f'\n[SUCCESS] Trained plate detector weights saved to: {prod_path}')
    trained_model = YOLO(str(prod_path))
    print(f'[VERIFIED] Model class mapping: {trained_model.names}')


if __name__ == '__main__':
    main()

