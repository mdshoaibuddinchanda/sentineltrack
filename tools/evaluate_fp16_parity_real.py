import json
import time
import cv2
import importlib
import torch
import numpy as np
from pathlib import Path

p0_models = importlib.import_module('00_foundation.streams.models')
p1_det = importlib.import_module('01_vehicle_detection.detector')
p3_det = importlib.import_module('03_plate_detection.detector')

FramePacket = p0_models.FramePacket
VehicleDetector = p1_det.VehicleDetector
PlateDetector = p3_det.PlateDetector

ROOT_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT_DIR / 'reports' / 'system_optimization' / 'resources'
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def compute_iou(box1, box2):
    # box: (x1, y1, x2, y2)
    ix1 = max(box1[0], box2[0])
    iy1 = max(box1[1], box2[1])
    ix2 = min(box1[2], box2[2])
    iy2 = min(box1[3], box2[3])

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih

    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0


def match_boxes(boxes32, boxes16, iou_thresh=0.50):
    # boxes: list of dict(box=(x1,y1,x2,y2), class_id=int, conf=float)
    matched = []
    unmatched32 = list(range(len(boxes32)))
    unmatched16 = list(range(len(boxes16)))

    iou_matrix = np.zeros((len(boxes32), len(boxes16)))
    for i, b32 in enumerate(boxes32):
        for j, b16 in enumerate(boxes16):
            iou_matrix[i, j] = compute_iou(b32['box'], b16['box'])

    while True:
        if iou_matrix.size == 0 or len(unmatched32) == 0 or len(unmatched16) == 0:
            break
        max_idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
        i, j = max_idx
        max_iou = iou_matrix[i, j]
        if max_iou < iou_thresh:
            break

        matched.append((boxes32[i], boxes16[j], max_iou))
        iou_matrix[i, :] = -1.0
        iou_matrix[:, j] = -1.0
        if i in unmatched32:
            unmatched32.remove(i)
        if j in unmatched16:
            unmatched16.remove(j)

    return matched, [boxes32[idx] for idx in unmatched32], [boxes16[idx] for idx in unmatched16]


def evaluate_real_fp16_parity():
    print('============================================================')
    print('EVALUATING REAL-IMAGE FP32 <-> FP16 OUTPUT PARITY')
    print('============================================================')

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f'Compute Device: {device}')

    val_dir = ROOT_DIR / 'datasets' / 'plate_detection' / 'images' / 'val'
    val_images = list(val_dir.glob('*.jpg'))[:50]
    print(f'Loaded {len(val_images)} real validation images from {val_dir}')

    if not val_images:
        print('No local validation images found.')
        return

    # 1. P1 Vehicle Detector Parity on Real Images
    print('\n1. Evaluating P1 Vehicle Detector (YOLO11m @ 960)...')
    det_fp32 = VehicleDetector(imgsz=960, device=device, half=False)
    det_fp16 = VehicleDetector(imgsz=960, device=device, half=True)

    p1_matched = []
    p1_total32 = 0
    p1_total16 = 0
    p1_unmatched32_count = 0
    p1_unmatched16_count = 0

    for img_p in val_images:
        frame = cv2.imread(str(img_p))
        if frame is None:
            continue
        pkt = FramePacket('cam-parity', 100.0, frame, 1)

        res32 = det_fp32.detect(pkt)
        res16 = det_fp16.detect(pkt)

        p1_total32 += len(res32)
        p1_total16 += len(res16)

        boxes32 = [{'box': (d.x1, d.y1, d.x2, d.y2), 'class_id': d.class_id, 'conf': d.confidence} for d in res32]
        boxes16 = [{'box': (d.x1, d.y1, d.x2, d.y2), 'class_id': d.class_id, 'conf': d.confidence} for d in res16]

        matched, u32, u16 = match_boxes(boxes32, boxes16, iou_thresh=0.50)
        p1_matched.extend(matched)
        p1_unmatched32_count += len(u32)
        p1_unmatched16_count += len(u16)

    p1_ious = [m[2] for m in p1_matched]
    p1_class_agree = sum(1 for m in p1_matched if m[0]['class_id'] == m[1]['class_id'])
    p1_conf_deltas = [abs(m[0]['conf'] - m[1]['conf']) for m in p1_matched]

    p1_report = {
        'model': 'YOLO11m (P1 Vehicle Detector)',
        'sample_count': len(val_images),
        'fp32_detection_count': p1_total32,
        'fp16_detection_count': p1_total16,
        'matched_detection_count': len(p1_matched),
        'class_agreement': round(p1_class_agree / max(len(p1_matched), 1), 4),
        'mean_iou': round(float(np.mean(p1_ious)), 4) if p1_ious else 0.0,
        'median_iou': round(float(np.median(p1_ious)), 4) if p1_ious else 0.0,
        'p05_iou': round(float(np.percentile(p1_ious, 5)), 4) if p1_ious else 0.0,
        'mean_confidence_delta': round(float(np.mean(p1_conf_deltas)), 4) if p1_conf_deltas else 0.0,
        'max_confidence_delta': round(float(np.max(p1_conf_deltas)), 4) if p1_conf_deltas else 0.0,
        'unmatched_fp32': p1_unmatched32_count,
        'unmatched_fp16': p1_unmatched16_count
    }
    p1_mean_iou = p1_report['mean_iou']
    p1_cls_agr = p1_report['class_agreement'] * 100
    p1_m_conf = p1_report['mean_confidence_delta']
    print(f'  P1 Matched: {len(p1_matched)} | Mean IoU: {p1_mean_iou} | Class Agreement: {p1_cls_agr:.1f}% | Mean Conf Delta: {p1_m_conf}')

    # 2. P3 Plate Detector Parity on Real Images
    print('\n2. Evaluating P3 Plate Detector (YOLO11s @ 960)...')
    plate_fp32 = PlateDetector(imgsz=960, device=device, half=False)
    plate_fp16 = PlateDetector(imgsz=960, device=device, half=True)

    p3_matched = []
    p3_total32 = 0
    p3_total16 = 0
    p3_unmatched32_count = 0
    p3_unmatched16_count = 0

    for img_p in val_images:
        frame = cv2.imread(str(img_p))
        if frame is None:
            continue

        res32 = plate_fp32.detect(frame)
        res16 = plate_fp16.detect(frame)

        p3_total32 += len(res32)
        p3_total16 += len(res16)

        boxes32 = [{'box': (d['x1'], d['y1'], d['x2'], d['y2']), 'class_id': 0, 'conf': d['confidence']} for d in res32]
        boxes16 = [{'box': (d['x1'], d['y1'], d['x2'], d['y2']), 'class_id': 0, 'conf': d['confidence']} for d in res16]

        matched, u32, u16 = match_boxes(boxes32, boxes16, iou_thresh=0.50)
        p3_matched.extend(matched)
        p3_unmatched32_count += len(u32)
        p3_unmatched16_count += len(u16)

    p3_ious = [m[2] for m in p3_matched]
    p3_class_agree = sum(1 for m in p3_matched if m[0]['class_id'] == m[1]['class_id'])
    p3_conf_deltas = [abs(m[0]['conf'] - m[1]['conf']) for m in p3_matched]

    p3_report = {
        'model': 'YOLO11s (P3 Plate Detector)',
        'sample_count': len(val_images),
        'fp32_detection_count': p3_total32,
        'fp16_detection_count': p3_total16,
        'matched_detection_count': len(p3_matched),
        'class_agreement': round(p3_class_agree / max(len(p3_matched), 1), 4),
        'mean_iou': round(float(np.mean(p3_ious)), 4) if p3_ious else 0.0,
        'median_iou': round(float(np.median(p3_ious)), 4) if p3_ious else 0.0,
        'p05_iou': round(float(np.percentile(p3_ious, 5)), 4) if p3_ious else 0.0,
        'mean_confidence_delta': round(float(np.mean(p3_conf_deltas)), 4) if p3_conf_deltas else 0.0,
        'max_confidence_delta': round(float(np.max(p3_conf_deltas)), 4) if p3_conf_deltas else 0.0,
        'unmatched_fp32': p3_unmatched32_count,
        'unmatched_fp16': p3_unmatched16_count
    }
    p3_mean_iou = p3_report['mean_iou']
    p3_cls_agr = p3_report['class_agreement'] * 100
    p3_m_conf = p3_report['mean_confidence_delta']
    print(f'  P3 Matched: {len(p3_matched)} | Mean IoU: {p3_mean_iou} | Class Agreement: {p3_cls_agr:.1f}% | Mean Conf Delta: {p3_m_conf}')

    final_report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
        'evaluation_type': 'FP32 <-> FP16 Output Parity on Real Local Validation Images',
        'p1_vehicle_detector': p1_report,
        'p3_plate_detector': p3_report
    }

    out_p = REPORTS_DIR / 'fp16_parity_real.json'
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=2)
    print(f'\nSaved real-image FP16 parity report to {out_p}')


if __name__ == '__main__':
    evaluate_real_fp16_parity()
