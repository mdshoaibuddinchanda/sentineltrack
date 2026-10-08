import sys
from pathlib import Path
from ultralytics import YOLO

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def validate_model(model_path: str):
    print(f'[VALIDATE] Evaluating plate detector: {model_path}')
    model = YOLO(model_path)
    dataset_yaml = ROOT_DIR / '03_plate_detection' / 'training' / 'dataset.yaml'

    metrics = model.val(
        data=str(dataset_yaml),
        imgsz=960,
        batch=8,
        device=0,
        split='val',
    )

    print('[VALIDATE] Evaluation results:')
    print(f'  mAP50: {metrics.box.map50:.4f}')
    print(f'  mAP50-95: {metrics.box.map:.4f}')
    print(f'  Precision: {metrics.box.mp:.4f}')
    print(f'  Recall: {metrics.box.mr:.4f}')


if __name__ == '__main__':
    model_to_val = sys.argv[1] if len(sys.argv) > 1 else 'models/plate/yolo11s_plate_v2.pt'
    validate_model(model_to_val)

