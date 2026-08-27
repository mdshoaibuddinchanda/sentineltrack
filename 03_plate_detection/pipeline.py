import sys
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import importlib
try:
    plate_models = importlib.import_module('03_plate_detection.models')
    PlateObservation = plate_models.PlateObservation
    cropper_mod = importlib.import_module('03_plate_detection.cropper')
    crop_vehicle = cropper_mod.crop_vehicle
    resize_for_plate_detection = cropper_mod.resize_for_plate_detection
    map_crop_to_full_frame = cropper_mod.map_crop_to_full_frame
    quality_mod = importlib.import_module('03_plate_detection.quality')
    compute_plate_quality = quality_mod.compute_plate_quality
    TrackPlateAccumulator = quality_mod.TrackPlateAccumulator
except Exception:
    from models import PlateObservation
    from cropper import crop_vehicle, resize_for_plate_detection, map_crop_to_full_frame
    from quality import compute_plate_quality, TrackPlateAccumulator


class PlateDetectionPipeline:
    """
    Coordinates vehicle cropping, high-res magnification, plate detection,
    coordinate re-projection to original frame, and quality evaluation.
    """

    def __init__(
        self,
        plate_detector,
        target_crop_width: int = 960,
        padding: float = 0.08,
        accumulator: Optional[TrackPlateAccumulator] = None,
    ):
        self.plate_detector = plate_detector
        self.target_crop_width = target_crop_width
        self.padding = padding
        self.accumulator = accumulator or TrackPlateAccumulator()

    def process(self, packet, tracks: list) -> list[PlateObservation]:
        """
        Processes tracked vehicles in a FramePacket:
        For each VehicleTrack -> Crop vehicle -> Enlarge -> Detect plate -> Re-project coords -> Score quality
        """
        observations = []
        frame = packet.frame
        fh, fw = frame.shape[:2]

        for track in tracks:
            # 1. Crop vehicle with border padding
            crop, cx1, cy1, cx2, cy2 = crop_vehicle(
                frame,
                x1=track.x1,
                y1=track.y1,
                x2=track.x2,
                y2=track.y2,
                padding=self.padding,
            )

            if crop is None or crop.size == 0:
                continue

            # 2. Enlarge crop for high-resolution plate localization
            resized_crop, scale = resize_for_plate_detection(
                crop,
                target_width=self.target_crop_width,
            )

            # 3. Detect plates inside vehicle crop
            raw_plates = self.plate_detector.detect(resized_crop)

            for p in raw_plates:
                # 4. Map plate box back into original CCTV full frame
                fx1, fy1, fx2, fy2, pw, ph = map_crop_to_full_frame(
                    local_x1=p['x1'],
                    local_y1=p['y1'],
                    local_x2=p['x2'],
                    local_y2=p['y2'],
                    crop_offset_x=cx1,
                    crop_offset_y=cy1,
                    scale_factor=scale,
                )

                # Clamp to original frame dimensions
                fx1 = max(0.0, min(float(fw), fx1))
                fy1 = max(0.0, min(float(fh), fy1))
                fx2 = max(0.0, min(float(fw), fx2))
                fy2 = max(0.0, min(float(fh), fy2))
                pw = max(0.0, fx2 - fx1)
                ph = max(0.0, fy2 - fy1)

                # Extract plate crop for quality assessment
                ix1, iy1, ix2, iy2 = int(round(fx1)), int(round(fy1)), int(round(fx2)), int(round(fy2))
                plate_img = frame[iy1:iy2, ix1:ix2]

                # 5. Evaluate sharpness and quality
                blur, bright, qscore = compute_plate_quality(
                    plate_image=plate_img,
                    width=pw,
                    height=ph,
                    confidence=p['confidence'],
                )

                obs = PlateObservation(
                    camera_id=packet.camera_id,
                    track_id=track.track_id,
                    stream_epoch=packet.stream_epoch,
                    pts_ms=packet.pts_ms,
                    confidence=p['confidence'],
                    x1=fx1,
                    y1=fy1,
                    x2=fx2,
                    y2=fy2,
                    width=pw,
                    height=ph,
                    vehicle_class=track.class_name,
                    vehicle_confidence=track.confidence,
                    plate_area=pw * ph,
                    blur_score=blur,
                    brightness_score=bright,
                    quality_score=qscore,
                )

                observations.append(obs)
                self.accumulator.add(obs, crop_image=plate_img)

        return observations

    def get_best_plate_crops(self, camera_id: str, stream_epoch: int, track_id: int) -> list:
        return self.accumulator.get_best_candidates(camera_id, stream_epoch, track_id)

    def reset_camera(self, camera_id: str):
        self.accumulator.reset_camera(camera_id)
