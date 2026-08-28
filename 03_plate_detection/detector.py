import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import torch
import numpy as np
from ultralytics import YOLO


class PlateDetector:
    """Dedicated License Plate Detector operating strictly on single-class plate models."""

    def __init__(
        self,
        model_path: str = "models/plate/production/best.pt",
        confidence: float = 0.20,
        imgsz: int = 960,
        device: Optional[str] = None,
        enforce_contract: bool = True,
        half: bool = False,
    ):
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.model_path = model_path
        self.confidence = confidence
        self.imgsz = imgsz
        self.half = half

        # Load YOLO model
        self.model = YOLO(model_path)

        # Startup Model Contract Assertion
        if enforce_contract:
            names = self.model.names
            valid_names = {"license_plate", "license-plate", "plate", "license_plates"}
            if len(names) != 1 or 0 not in names or names[0] not in valid_names:
                raise RuntimeError(
                    f"Wrong model loaded at '{model_path}'. Expected {{0: 'license_plate'}}, got: {names}"
                )

    def detect(self, vehicle_crop: np.ndarray) -> List[Dict[str, float]]:
        """Runs plate detection inference on a single vehicle crop image."""
        batch_res = self.detect_batch([vehicle_crop])
        return batch_res[0] if batch_res else []

    def detect_batch(self, vehicle_crops: List[np.ndarray]) -> List[List[Dict[str, float]]]:
        """
        Runs batch plate detection inference across a list of vehicle crops.
        Returns a list of detected plate lists.
        """
        valid_indices = []
        valid_crops = []

        for idx, crop in enumerate(vehicle_crops):
            if crop is not None and crop.size > 0:
                valid_indices.append(idx)
                valid_crops.append(crop)

        all_results: List[List[Dict[str, float]]] = [[] for _ in range(len(vehicle_crops))]
        if not valid_crops:
            return all_results

        results = self.model.predict(
            source=valid_crops,
            conf=self.confidence,
            imgsz=self.imgsz,
            device=self.device,
            half=self.half,
            verbose=False,
        )

        for orig_idx, result in zip(valid_indices, results):
            plates = []
            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    class_id = int(box.cls.item())
                    if class_id != 0:
                        continue

                    conf = float(box.conf.item())
                    coords = box.xyxy[0].cpu().tolist()
                    x1, y1, x2, y2 = float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3])

                    bw = max(0.0, x2 - x1)
                    bh = max(0.0, y2 - y1)

                    plates.append({
                        "confidence": conf,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                    })

            all_results[orig_idx] = plates

        return all_results
