import os
import json
import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_detection'
TEST_IMG_DIR = DATASET_DIR / 'images' / 'test'
TEST_LBL_DIR = DATASET_DIR / 'labels' / 'test'
PUBLIC_DIR = DATASET_DIR / 'sources' / 'public_indian'
REPORT_DIR = ROOT_DIR / 'reports' / 'plate_detection'


def compute_iou(box1, box2):
    # box: [x1, y1, x2, y2]
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter = inter_w * inter_h

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def evaluate_production_model(model_path: str = 'models/plate/production/best.pt', conf_thresh: float = 0.20):
    print(f'[EVALUATION] Evaluating production plate detector: {model_path}')
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    model = YOLO(model_path)
    print(f'[EVALUATION] Model classes: {model.names}')
    assert len(model.names) == 1 and model.names[0] == 'license_plate', 'Model violates single-class contract!'

    # Load metadata tags if available
    metadata_map = {}
    meta_path = PUBLIC_DIR / 'metadata.json'
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta_list = json.load(f)
            for m in meta_list:
                metadata_map[m['image']] = m.get('tags', '').split(',')

    test_imgs = sorted(list(TEST_IMG_DIR.glob('*.jpg')))
    print(f'[EVALUATION] Testing on {len(test_imgs)} REAL test images...')

    tp = 0
    fp = 0
    fn = 0

    category_stats = {}

    for img_p in test_imgs:
        img_name = img_p.name
        lbl_p = TEST_LBL_DIR / img_p.with_suffix('.txt').name

        img = cv2.imread(str(img_p))
        h, w = img.shape[:2]

        # Ground truth boxes
        gt_boxes = []
        if lbl_p.exists():
            with open(lbl_p, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls_id, xc, yc, nw, nh = map(float, parts[:5])
                        if int(cls_id) == 0:
                            gx1 = (xc - nw / 2.0) * w
                            gy1 = (yc - nh / 2.0) * h
                            gx2 = (xc + nw / 2.0) * w
                            gy2 = (yc + nh / 2.0) * h
                            gt_boxes.append([gx1, gy1, gx2, gy2])

        # Prediction
        results = model.predict(source=img, conf=conf_thresh, imgsz=960, verbose=False)
        pred_boxes = []
        if results and results[0].boxes is not None:
            for b in results[0].boxes:
                if int(b.cls.item()) == 0:
                    pred_boxes.append(b.xyxy[0].cpu().tolist())

        # Match GT and Preds
        matched_gt = [False] * len(gt_boxes)
        for pbox in pred_boxes:
            best_iou = 0.0
            best_gt_idx = -1
            for g_idx, gbox in enumerate(gt_boxes):
                if not matched_gt[g_idx]:
                    iou = compute_iou(pbox, gbox)
                    if iou > best_iou:
                        best_iou = iou
                        best_gt_idx = g_idx

            if best_iou >= 0.5:
                tp += 1
                matched_gt[best_gt_idx] = True
            else:
                fp += 1

        unmatched_fn = sum(1 for m in matched_gt if not m)
        fn += unmatched_fn

        # Track category statistics
        tags = metadata_map.get(img_name, ['standard_white'])
        for tag in tags:
            tag = tag.strip()
            if not tag: continue
            if tag not in category_stats:
                category_stats[tag] = {'total_gt': 0, 'detected': 0}
            category_stats[tag]['total_gt'] += len(gt_boxes)
            category_stats[tag]['detected'] += sum(1 for m in matched_gt if m)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    eval_report = {
        'model_path': model_path,
        'test_set_type': 'REAL ONLY (public Indian vehicle CCTV samples)',
        'test_images_count': len(test_imgs),
        'total_gt_plates': tp + fn,
        'true_positives': tp,
        'false_positives': fp,
        'false_negatives': fn,
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1_score': round(f1, 4),
        'category_recall': {
            cat: {
                'total': data['total_gt'],
                'detected': data['detected'],
                'recall': round(data['detected'] / data['total_gt'], 4) if data['total_gt'] > 0 else 0.0
            }
            for cat, data in category_stats.items()
        }
    }

    report_path = REPORT_DIR / 'real_plate_evaluation.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(eval_report, f, indent=2)

    print('\n================ PRODUCTION REAL PLATE EVALUATION ================')
    print(f'Test Images Evaluated: {len(test_imgs)} (100% REAL)')
    print(f'True Positives: {tp} | False Positives: {fp} | False Negatives: {fn}')
    print(f'Precision: {precision:.2%} | Recall: {recall:.2%} | F1-Score: {f1:.2%}')
    print('\nBreakdown by Plate Difficulty & Type:')
    for cat, metrics in eval_report['category_recall'].items():
        print(f'  - {cat:<20}: {metrics["detected"]}/{metrics["total"]} ({metrics["recall"]:.1%})')
    print(f'\nFull report saved to: {report_path}')
    print('==================================================================\n')

    return eval_report


if __name__ == '__main__':
    evaluate_production_model()
