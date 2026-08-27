import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import importlib
det_mod = importlib.import_module('03_plate_detection.detector')
PlateDetector = det_mod.PlateDetector


def test_plate_model_contract_rejects_coco_model():
    """Ensures that loading an 80-class COCO model raises RuntimeError at startup."""
    with patch.object(det_mod, 'YOLO') as mock_yolo:
        mock_instance = MagicMock()
        # Mock 80 COCO classes
        mock_instance.names = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 4: 'airplane', 5: 'bus'}
        mock_yolo.return_value = mock_instance

        with pytest.raises(RuntimeError, match='Wrong model loaded'):
            PlateDetector(model_path='dummy_coco.pt', enforce_contract=True)


def test_plate_model_contract_accepts_license_plate_model():
    """Ensures that loading a 1-class license plate model passes successfully."""
    with patch.object(det_mod, 'YOLO') as mock_yolo:
        mock_instance = MagicMock()
        mock_instance.names = {0: 'license_plate'}
        mock_yolo.return_value = mock_instance

        detector = PlateDetector(model_path='models/plate/production/best.pt', enforce_contract=True)
        assert len(detector.model.names) == 1
        assert detector.model.names[0] == 'license_plate'

