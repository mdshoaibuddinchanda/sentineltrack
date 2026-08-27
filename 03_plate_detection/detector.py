import sys
from pathlib import Path
from typing import Optional

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
    ):
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.model_path = model_path
        self.confidence = confidence
        self.imgsz = imgsz

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


    def detect(self, vehicle_crop: np.ndarray) -> list[dict]:
        """
        Runs plate detection inference on a vehicle crop image.
        Returns list of dicts: [{'confidence': float, 'x1': float, 'y1': float, 'x2': float, 'y2': float}]
        """
        if vehicle_crop is None or vehicle_crop.size == 0:
            return []

        results = self.model.predict(
            source=vehicle_crop,
            conf=self.confidence,
            imgsz=self.imgsz,
            device=self.device,
            verbose=False,
        )

        plates = []
        if not results:
            return plates

        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return plates

        for box in result.boxes:
            # Enforce single class check: class 0 = license_plate
            class_id = int(box.cls.item())
            if class_id != 0:
                continue

            conf = float(box.conf.item())
            coords = box.xyxy[0].cpu().tolist()
            x1, y1, x2, y2 = float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3])

            bw = max(0.0, x2 - x1)
            bh = max(0.0, y2 - y1)

            # Sanity filter: Plates cannot be taller than they are wide (aspect ratio >= 1.0)
            if bh > 0 and (bw / bh) < 0.9:
                continue

            plates.append({
                "confidence": conf,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
            })

        return plates

