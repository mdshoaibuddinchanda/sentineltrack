import importlib
import numpy as np

p3_models = importlib.import_module('03_plate_detection.models')
p4_pipe = importlib.import_module('04_plate_ocr.pipeline')
mock_mod = importlib.import_module('04_plate_ocr.recognizers.mock_rec')

PlateObservation = p3_models.PlateObservation
PlateOCRPipeline = p4_pipe.PlateOCRPipeline
compute_crop_hash = p4_pipe.compute_crop_hash
MockPlateRecognizer = mock_mod.MockPlateRecognizer


def test_crop_hash_deduplication():
    img1 = np.full((64, 256, 3), 200, dtype=np.uint8)
    img2 = np.full((64, 256, 3), 200, dtype=np.uint8)
    img3 = np.full((64, 256, 3), 50, dtype=np.uint8)

    h1 = compute_crop_hash(img1)
    h2 = compute_crop_hash(img2)
    h3 = compute_crop_hash(img3)

    assert h1 == h2
    assert h1 != h3


def test_pipeline_end_to_end_with_mock():
    mock = MockPlateRecognizer(default_text='GJ01AB1234', default_conf=0.95)
    pipeline = PlateOCRPipeline(recognizer=mock, enable_deduplication=True)

    obs1 = PlateObservation(
        camera_id='cam1',
        track_id=10,
        stream_epoch=1,
        pts_ms=0.0,
        confidence=0.85,
        x1=100, y1=200, x2=220, y2=240,
        width=120, height=40,
        vehicle_class='car',
        vehicle_confidence=0.90,
        quality_score=0.85
    )
    crop1 = np.full((40, 120, 3), 220, dtype=np.uint8)
    hyp1 = pipeline.process_observation(obs1, crop1)
    assert hyp1 is not None
    assert hyp1.normalized_text == 'GJ01AB1234'

    # Duplicate crop: should be deduplicated
    obs2 = PlateObservation(
        camera_id='cam1',
        track_id=10,
        stream_epoch=1,
        pts_ms=150.0,
        confidence=0.85,
        x1=100, y1=200, x2=220, y2=240,
        width=120, height=40,
        vehicle_class='car',
        vehicle_confidence=0.90,
        quality_score=0.85
    )
    hyp2 = pipeline.process_observation(obs2, crop1)
    assert hyp2 is None

    # Single observation -> CANDIDATE (requires min_support=2)
    res_single = pipeline.get_track_result('cam1', 1, 10)
    assert res_single.status == 'CANDIDATE'

    # Corroborating second observation with distinct crop
    obs3 = PlateObservation(
        camera_id='cam1',
        track_id=10,
        stream_epoch=1,
        pts_ms=300.0,
        confidence=0.88,
        x1=105, y1=202, x2=225, y2=242,
        width=120, height=40,
        vehicle_class='car',
        vehicle_confidence=0.92,
        quality_score=0.88
    )
    crop2 = np.full((40, 120, 3), 215, dtype=np.uint8)
    hyp3 = pipeline.process_observation(obs3, crop2)
    assert hyp3 is not None

    res = pipeline.get_track_result('cam1', 1, 10)
    assert res.is_resolved is True
    assert res.best_text == 'GJ01AB1234'
    assert res.support_count >= 2


def test_pipeline_camera_reset_clears_state():
    mock = MockPlateRecognizer(default_text='GJ01AB1234')
    pipeline = PlateOCRPipeline(recognizer=mock)

    obs = PlateObservation(
        camera_id='cam1',
        track_id=10,
        stream_epoch=1,
        pts_ms=0.0,
        confidence=0.85,
        x1=100, y1=200, x2=220, y2=240,
        width=120, height=40,
        vehicle_class='car',
        vehicle_confidence=0.90,
        quality_score=0.85
    )
    crop = np.full((40, 120, 3), 220, dtype=np.uint8)
    pipeline.process_observation(obs, crop)

    assert ('cam1', 1, 10) in pipeline.track_hypotheses
    pipeline.reset_camera('cam1')
    assert ('cam1', 1, 10) not in pipeline.track_hypotheses
