import cv2
import numpy as np
from .rectification import rectify_plate_perspective


def resize_aspect_ratio(image: np.ndarray, target_height: int = 64, max_width: int = 320) -> np.ndarray:
    """Resizes crop preserving aspect ratio with clean interpolation."""
    if image is None or image.size == 0:
        return image

    h, w = image.shape[:2]
    scale = target_height / max(h, 1)
    new_w = max(int(w * scale), 16)
    new_w = min(new_w, max_width)

    resized = cv2.resize(image, (new_w, target_height), interpolation=cv2.INTER_CUBIC)
    return resized


def preprocess_crop(
    crop: np.ndarray,
    variant: str = 'raw',
    target_height: int = 64
) -> tuple[np.ndarray, dict]:
    """
    Applies configurable image preprocessing variants for OCR recognition.
    Returns (preprocessed_image, metadata).
    """
    if crop is None or crop.size == 0:
        return crop, {'variant': variant, 'applied': False}

    meta = {'variant': variant, 'applied': True, 'original_shape': crop.shape}
    img = crop.copy()

    if variant == 'raw':
        processed = resize_aspect_ratio(img, target_height=target_height)

    elif variant == 'gray':
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        norm = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        resized = resize_aspect_ratio(norm, target_height=target_height)
        processed = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)

    elif variant == 'clahe':
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)
        resized = resize_aspect_ratio(enhanced, target_height=target_height)
        processed = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)

    elif variant == 'sharpen':
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        blur = cv2.GaussianBlur(gray, (0, 0), 2.0)
        unsharp = cv2.addWeighted(gray, 1.5, blur, -0.5, 0)
        resized = resize_aspect_ratio(unsharp, target_height=target_height)
        processed = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)

    elif variant == 'rectify':
        rectified, applied, conf = rectify_plate_perspective(img)
        meta['rectification_applied'] = applied
        meta['rectification_confidence'] = conf
        processed = resize_aspect_ratio(rectified, target_height=target_height)

    else:
        processed = resize_aspect_ratio(img, target_height=target_height)

    return processed, meta
