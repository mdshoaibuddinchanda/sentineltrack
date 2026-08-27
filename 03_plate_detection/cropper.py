import cv2
import numpy as np


def crop_vehicle(
    frame: np.ndarray,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    padding: float = 0.08,
) -> tuple[np.ndarray, int, int, int, int]:
    """
    Crops a vehicle bounding box with boundary padding to preserve bumper edges.
    Returns: (crop, crop_x1, crop_y1, crop_x2, crop_y2)
    """
    h, w = frame.shape[:2]
    bw = x2 - x1
    bh = y2 - y1

    px = bw * padding
    py = bh * padding

    cx1 = max(0, int(x1 - px))
    cy1 = max(0, int(y1 - py))
    cx2 = min(w, int(x2 + px))
    cy2 = min(h, int(y2 + py))

    crop = frame[cy1:cy2, cx1:cx2]
    return crop, cx1, cy1, cx2, cy2


def resize_for_plate_detection(
    crop: np.ndarray,
    target_width: int = 960,
) -> tuple[np.ndarray, float]:
    """
    Enlarges a vehicle crop to target_width for high-resolution plate detection.
    Returns: (resized_crop, scale_factor)
    """
    if crop is None or crop.size == 0:
        return crop, 1.0

    h, w = crop.shape[:2]
    if w == 0 or h == 0:
        return crop, 1.0

    scale = float(target_width) / float(w)
    new_height = max(1, int(round(h * scale)))

    resized = cv2.resize(
        crop,
        (target_width, new_height),
        interpolation=cv2.INTER_CUBIC,
    )
    return resized, scale


def map_crop_to_full_frame(
    local_x1: float,
    local_y1: float,
    local_x2: float,
    local_y2: float,
    crop_offset_x: int,
    crop_offset_y: int,
    scale_factor: float = 1.0,
) -> tuple[float, float, float, float, float, float]:
    """
    Maps bounding box coordinates from resized crop space back to the original full CCTV frame.
    Returns: (full_x1, full_y1, full_x2, full_y2, width, height)
    """
    if scale_factor <= 0:
        scale_factor = 1.0

    unscaled_x1 = local_x1 / scale_factor
    unscaled_y1 = local_y1 / scale_factor
    unscaled_x2 = local_x2 / scale_factor
    unscaled_y2 = local_y2 / scale_factor

    full_x1 = crop_offset_x + unscaled_x1
    full_y1 = crop_offset_y + unscaled_y1
    full_x2 = crop_offset_x + unscaled_x2
    full_y2 = crop_offset_y + unscaled_y2

    width = max(0.0, full_x2 - full_x1)
    height = max(0.0, full_y2 - full_y1)

    return full_x1, full_y1, full_x2, full_y2, width, height
