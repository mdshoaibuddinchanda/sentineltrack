import cv2
import numpy as np


def blur_score(image: np.ndarray) -> float:
    """Computes Laplacian variance as a proxy for sharpness (higher = sharper)."""
    if image is None or image.size == 0:
        return 0.0
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def brightness_score(image: np.ndarray) -> float:
    """Computes average brightness in range [0, 255]."""
    if image is None or image.size == 0:
        return 0.0
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return float(np.mean(gray))


def compute_plate_quality(
    plate_image: np.ndarray,
    width: float,
    height: float,
    confidence: float,
) -> tuple[float, float, float]:
    """
    Evaluates quality of a detected plate crop.
    Returns: (blur, brightness, composite_quality_score)
    """
    if plate_image is None or plate_image.size == 0 or width <= 0 or height <= 0:
        return 0.0, 0.0, 0.0

    blur = blur_score(plate_image)
    bright = brightness_score(plate_image)

    # Resolution score factor: higher area & width improves OCR
    area = width * height
    res_factor = min(1.0, area / 2500.0)  # ~50x50 benchmark

    # Sharpness score factor: normalized ~100 Laplacian var
    sharpness_factor = min(1.0, blur / 100.0)

    # Brightness adequacy penalty if severely underexposed (<30) or overexposed (>235)
    brightness_factor = 1.0
    if bright < 30.0:
        brightness_factor = max(0.1, bright / 30.0)
    elif bright > 235.0:
        brightness_factor = max(0.1, (255.0 - bright) / 20.0)

    # Composite score [0.0, 1.0]
    composite = (
        0.35 * confidence +
        0.30 * sharpness_factor +
        0.20 * res_factor +
        0.15 * brightness_factor
    )

    return round(blur, 2), round(bright, 2), round(composite, 4)


class TrackPlateAccumulator:
    """
    Accumulates and ranks plate observation candidates per vehicle track.
    Retains only the top K highest quality plate observations per track.
    """

    def __init__(self, max_candidates_per_track: int = 10):
        self.candidates: dict[tuple[str, int, int], list] = {}
        self.max_candidates = max_candidates_per_track

    def add(self, observation, crop_image: np.ndarray | None = None):
        key = (
            observation.camera_id,
            observation.stream_epoch,
            observation.track_id,
        )
        if key not in self.candidates:
            self.candidates[key] = []

        item = {
            "observation": observation,
            "crop": crop_image,
            "quality": observation.quality_score,
            "pts_ms": observation.pts_ms,
        }
        self.candidates[key].append(item)

        # Sort descending by quality score and retain top K
        self.candidates[key].sort(key=lambda x: x["quality"], reverse=True)
        if len(self.candidates[key]) > self.max_candidates:
            self.candidates[key] = self.candidates[key][:self.max_candidates]

    def get_best_candidates(self, camera_id: str, stream_epoch: int, track_id: int) -> list:
        key = (camera_id, stream_epoch, track_id)
        return self.candidates.get(key, [])

    def get_all_tracks(self) -> list[tuple[str, int, int]]:
        return list(self.candidates.keys())

    def reset_camera(self, camera_id: str):
        to_remove = [k for k in self.candidates if k[0] == camera_id]
        for k in to_remove:
            del self.candidates[k]

