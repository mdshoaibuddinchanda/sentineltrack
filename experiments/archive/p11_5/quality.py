"""Interpretable plate-crop quality features for P11.5 experiments."""

from __future__ import annotations

from typing import Any


def crop_quality(crop: Any, detector_confidence: float | None = None) -> dict[str, float]:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    if crop is None or getattr(crop, "size", 0) == 0:
        return {"width": 0.0, "height": 0.0, "area": 0.0, "sharpness": 0.0, "brightness": 0.0, "contrast": 0.0, "score": 0.0}
    height, width = crop.shape[:2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    size_score = min(1.0, (width * height) / 12000.0)
    sharp_score = min(1.0, sharpness / 500.0)
    contrast_score = min(1.0, contrast / 64.0)
    exposure_score = max(0.0, 1.0 - abs(brightness - 128.0) / 128.0)
    detector_score = 1.0 if detector_confidence is None else max(0.0, min(1.0, detector_confidence))
    score = 0.30 * size_score + 0.30 * sharp_score + 0.20 * contrast_score + 0.10 * exposure_score + 0.10 * detector_score
    return {"width": float(width), "height": float(height), "area": float(width * height), "sharpness": sharpness, "brightness": brightness, "contrast": contrast, "score": round(score, 6)}
