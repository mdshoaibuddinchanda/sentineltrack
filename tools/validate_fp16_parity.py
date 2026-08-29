import torch
import numpy as np
import importlib
from pathlib import Path

p0_models = importlib.import_module('00_foundation.streams.models')
p1_det = importlib.import_module('01_vehicle_detection.detector')
p3_det = importlib.import_module('03_plate_detection.detector')

FramePacket = p0_models.FramePacket
VehicleDetector = p1_det.VehicleDetector
PlateDetector = p3_det.PlateDetector


def compute_iou(box1, box2):
    # box: (x1, y1, x2, y2)
    ix1 = max(box1[0], box2[0])
    iy1 = max(box1[1], box2[1])
    ix2 = min(box1[2], box2[2])
    iy2 = min(box1[3], box2[3])

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0


def test_p1_vehicle_fp16_parity():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device != 'cuda':
        return  # FP16 is only active on CUDA

    det_fp32 = VehicleDetector(imgsz=640, device=device, half=False)
    det_fp16 = VehicleDetector(imgsz=640, device=device, half=True)

    # Test image with synthetic vehicle shape
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    img[200:500, 400:800] = 180  # Rectangular object
    pkt = FramePacket('cam-parity', 100.0, img, 1)

    dets_32 = det_fp32.detect(pkt)
    dets_16 = det_fp16.detect(pkt)

    # Both should agree on detection count
    assert len(dets_32) == len(dets_16)
    for d32, d16 in zip(dets_32, dets_16):
        assert d32.class_id == d16.class_id
        iou = compute_iou((d32.x1, d32.y1, d32.x2, d32.y2), (d16.x1, d16.y1, d16.x2, d16.y2))
        assert iou >= 0.95
        assert abs(d32.confidence - d16.confidence) <= 0.08


def test_p3_plate_fp16_parity():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device != 'cuda':
        return  # FP16 is only active on CUDA

    plate_fp32 = PlateDetector(imgsz=640, device=device, half=False)
    plate_fp16 = PlateDetector(imgsz=640, device=device, half=True)

    crop = np.zeros((480, 640, 3), dtype=np.uint8)
    crop[200:300, 200:450] = 220

    res_32 = plate_fp32.detect(crop)
    res_16 = plate_fp16.detect(crop)

    assert len(res_32) == len(res_16)
    for p32, p16 in zip(res_32, res_16):
        iou = compute_iou((p32['x1'], p32['y1'], p32['x2'], p32['y2']), (p16['x1'], p16['y1'], p16['x2'], p16['y2']))
        assert iou >= 0.90
        assert abs(p32['confidence'] - p16['confidence']) <= 0.08
