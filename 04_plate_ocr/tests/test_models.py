import importlib

models_mod = importlib.import_module('04_plate_ocr.models')
OCRHypothesis = models_mod.OCRHypothesis
TrackOCRResult = models_mod.TrackOCRResult


def test_ocr_hypothesis_creation():
    hyp = OCRHypothesis(
        camera_id='cam1',
        track_id=10,
        stream_epoch=1,
        pts_ms=150.0,
        raw_text='GJ-01-AB-1234',
        normalized_text='GJ01AB1234',
        ocr_confidence=0.92,
        crop_quality=0.85,
        grammar_score=1.0,
        preprocess_variant='clahe',
        recognizer_name='easyocr_crnn',
        character_confidences=[0.92] * 10,
        plate_width=120,
        plate_height=35
    )
    assert hyp.camera_id == 'cam1'
    assert hyp.track_id == 10
    assert hyp.normalized_text == 'GJ01AB1234'
    assert hyp.weighted_score > 0.85


def test_track_ocr_result_properties():
    res = TrackOCRResult(
        camera_id='cam1',
        track_id=10,
        stream_epoch=1,
        first_pts_ms=0.0,
        last_pts_ms=450.0,
        best_text='GJ01AB1234',
        confidence=0.95,
        support_count=3,
        total_hypotheses=3,
        status='RESOLVED',
        alternatives=[('GJ01AB1238', 0.20)],
        hypotheses=[]
    )
    assert res.is_resolved is True
    assert res.best_text == 'GJ01AB1234'
    assert res.confidence == 0.95

    unresolved = TrackOCRResult(
        camera_id='cam1',
        track_id=11,
        stream_epoch=1,
        first_pts_ms=0.0,
        last_pts_ms=0.0,
        best_text=None,
        confidence=0.10,
        support_count=0,
        total_hypotheses=1,
        status='INSUFFICIENT_EVIDENCE'
    )
    assert unresolved.is_resolved is False
