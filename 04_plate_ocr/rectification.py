import cv2
import numpy as np


def rectify_plate_perspective(crop: np.ndarray, min_area_ratio: float = 0.40) -> tuple[np.ndarray, bool, float]:
    """
    Attempts conservative perspective rectification of a license plate crop.
    Returns (rectified_or_original_crop, rectification_applied, confidence).
    If no clean 4-corner polygon is detected, safely returns original crop.
    """
    if crop is None or crop.size == 0:
        return crop, False, 0.0

    h, w = crop.shape[:2]
    if h < 16 or w < 32:
        return crop, False, 0.0

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return crop, False, 0.0

    best_poly = None
    max_area = 0
    crop_area = h * w

    for c in contours:
        area = cv2.contourArea(c)
        if area < crop_area * min_area_ratio:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.03 * peri, True)
        if len(approx) == 4 and area > max_area:
            max_area = area
            best_poly = approx

    if best_poly is None:
        return crop, False, 0.0

    # Order points: top-left, top-right, bottom-right, bottom-left
    pts = best_poly.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)

    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]

    src = np.array([tl, tr, br, bl], dtype=np.float32)

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_w = max(int(max(width_a, width_b)), 64)

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_h = max(int(max(height_a, height_b)), 24)

    dst = np.array([
        [0, 0],
        [max_w - 1, 0],
        [max_w - 1, max_h - 1],
        [0, max_h - 1]
    ], dtype=np.float32)

    try:
        M = cv2.getPerspectiveTransform(src, dst)
        rectified = cv2.warpPerspective(crop, M, (max_w, max_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        confidence = float(max_area / crop_area)
        return rectified, True, round(confidence, 3)
    except Exception:
        return crop, False, 0.0
