import sys
import cv2
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = ROOT_DIR / 'reports' / 'plate_detection'


def categorize_and_save_plate(
    plate_obs,
    plate_crop: cv2.typing.MatLike,
    camera_id: str,
    frame_idx: int,
):
    """Saves candidate plate crops into categorized diagnosis galleries."""
    if plate_crop is None or plate_crop.size == 0:
        return

    subfolder = 'successful'
    if plate_obs.height < 12.0:
        subfolder = 'tiny_plate'
    elif plate_obs.blur_score < 30.0:
        subfolder = 'blur'
    elif plate_obs.brightness_score < 40.0:
        subfolder = 'night'
    elif plate_obs.vehicle_class == 'motorcycle':
        subfolder = 'motorcycle'
    elif plate_obs.aspect_ratio < 2.0 or plate_obs.aspect_ratio > 5.0:
        subfolder = 'angled'

    save_dir = REPORTS_DIR / subfolder
    save_dir.mkdir(parents=True, exist_ok=True)

    filename = f'{camera_id}_track{plate_obs.track_id}_f{frame_idx}_q{int(plate_obs.quality_score*100)}.jpg'
    save_path = save_dir / filename
    cv2.imwrite(str(save_path), plate_crop)
    return str(save_path)
