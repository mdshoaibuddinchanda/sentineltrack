import sys
import cv2
import importlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

pipe_mod = importlib.import_module('04_plate_ocr.pipeline')
PlateOCRPipeline = pipe_mod.PlateOCRPipeline


def test_track_simulation(image_paths: list[str], camera_id: str = 'cam1', track_id: int = 1):
    pipeline = PlateOCRPipeline(default_variant='gray')

    print(f'================ SIMULATED TRACK OCR TEST ================')
    print(f'Simulating track #{track_id} on {camera_id} with {len(image_paths)} observations...')

    p3_models = importlib.import_module('03_plate_detection.models')
    PlateObservation = p3_models.PlateObservation


    for i, path in enumerate(image_paths):
        img = cv2.imread(path)
        if img is None:
            continue
        obs = PlateObservation(
            camera_id=camera_id,
            track_id=track_id,
            stream_epoch=1,
            pts_ms=float(i * 150.0),
            confidence=0.88,
            x1=10, y1=10, x2=100, y2=40,
            width=90, height=30,
            vehicle_class='car',
            vehicle_confidence=0.90,
            quality_score=0.75 - i * 0.05
        )
        hyp = pipeline.process_observation(obs, img)
        if hyp:
            print(f'  Frame #{i+1:<2} | Raw: \"{hyp.raw_text}\" | Norm: \"{hyp.normalized_text}\" | Conf: {hyp.ocr_confidence:.2f} | Gram: {hyp.grammar_score:.2f}')

    res = pipeline.get_track_result(camera_id, 1, track_id)
    print(f'\n[CONSENSUS RESULT]')
    print(f'  Resolved Text: \"{res.best_text}\"')
    print(f'  Confidence:    {res.confidence:.4f}')
    print(f'  Support Count: {res.support_count}/{res.total_hypotheses}')
    print(f'  Status:        {res.status}')
    print(f'  Alternatives:  {res.alternatives}')
    print('==========================================================')


if __name__ == '__main__':
    val_imgs = sorted(list((ROOT_DIR / 'datasets' / 'plate_ocr' / 'images' / 'val').glob('*.jpg')))[:4]
    if val_imgs:
        test_track_simulation([str(p) for p in val_imgs])
