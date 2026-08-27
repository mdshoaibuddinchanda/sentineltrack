import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import torch
import numpy as np
from unittest.mock import patch, MagicMock

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
from pipeline import VehicleDetectionPipeline
from benchmark import VehicleDetectionBenchmark


class MockBox:
    def __init__(self, cls_id: int, conf: float, xyxy: list):
        self._cls = torch.tensor(float(cls_id))
        self._conf = torch.tensor(conf)
        self._xyxy = torch.tensor([xyxy])

    @property
    def cls(self):
        return self._cls

    @property
    def conf(self):
        return self._conf

    @property
    def xyxy(self):
        return self._xyxy


def test_vehicle_detector_filters_non_vehicles():
    # Simulate YOLO predicting:
    # 0: person (should be filtered out)
    # 2: car (should be kept)
    # 3: motorcycle (should be kept)
    # 16: dog (should be filtered out)
    # 7: truck (should be kept)
    boxes = [
        MockBox(0, 0.90, [10, 10, 50, 100]),     # person
        MockBox(2, 0.85, [100, 100, 300, 250]),  # car
        MockBox(3, 0.78, [400, 200, 480, 290]),  # motorcycle
        MockBox(16, 0.95, [50, 50, 80, 80]),     # dog
        MockBox(7, 0.88, [500, 100, 800, 400]),  # truck
    ]

    mock_result = MagicMock()
    mock_result.boxes = boxes

    with patch('detector.YOLO') as mock_yolo_cls:
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.predict.return_value = [mock_result]
        mock_yolo_cls.return_value = mock_yolo_instance

        detector = VehicleDetector(model_path='dummy.pt')
        packet = FramePacket(
            camera_id='cam_test',
            pts_ms=12345.67,
            frame=np.zeros((720, 1280, 3), dtype=np.uint8),
            stream_epoch=2,
        )

        detections = detector.detect(packet)

        # Only car (2), motorcycle (3), and truck (7) should survive
        assert len(detections) == 3

        # Verify preservation of PTS, camera_id, stream_epoch
        for d in detections:
            assert d.camera_id == 'cam_test'
            assert d.pts_ms == 12345.67
            assert d.stream_epoch == 2

        classes_found = [d.class_name for d in detections]
        assert classes_found == ['car', 'motorcycle', 'truck']
        assert 'person' not in classes_found
        assert 'dog' not in classes_found


def test_vehicle_detection_pipeline():
    with patch('detector.YOLO') as mock_yolo_cls:
        mock_yolo_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes = [MockBox(2, 0.92, [50, 50, 200, 150])]
        mock_yolo_instance.predict.return_value = [mock_result]
        mock_yolo_cls.return_value = mock_yolo_instance

        detector = VehicleDetector(model_path='dummy.pt')
        pipeline = VehicleDetectionPipeline(detector)

        packet = FramePacket(
            camera_id='cam_p1',
            pts_ms=500.0,
            frame=np.zeros((100, 100, 3), dtype=np.uint8),
            stream_epoch=0,
        )

        dets = pipeline.process(packet)
        assert len(dets) == 1
        assert dets[0].class_name == 'car'
        assert round(dets[0].confidence, 2) == 0.92



def test_vehicle_detection_benchmark():
    with patch('detector.YOLO') as mock_yolo_cls:
        mock_yolo_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes = [
            MockBox(2, 0.90, [10, 10, 50, 50]),
            MockBox(5, 0.85, [60, 60, 120, 120]),  # bus
        ]
        mock_yolo_instance.predict.return_value = [mock_result]
        mock_yolo_cls.return_value = mock_yolo_instance

        detector = VehicleDetector(model_path='dummy.pt')
        benchmarker = VehicleDetectionBenchmark(detector)

        packets = [
            FramePacket('c1', 100.0, np.zeros((480, 640, 3), dtype=np.uint8), 0),
            FramePacket('c1', 200.0, np.zeros((480, 640, 3), dtype=np.uint8), 0),
            FramePacket('c1', 300.0, np.zeros((480, 640, 3), dtype=np.uint8), 0),
        ]

        result = benchmarker.run_on_packets(packets, camera_id='c1')
        assert result.total_frames == 3
        assert result.total_detections == 6
        assert result.class_counts == {'car': 3, 'bus': 3}
        assert result.resolution == '640x480'
        assert result.avg_inference_ms >= 0.0
        assert result.p50_inference_ms >= 0.0
        assert result.p95_inference_ms >= 0.0
