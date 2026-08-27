import importlib

models_mod = importlib.import_module('04_plate_ocr.models')
vote_mod = importlib.import_module('04_plate_ocr.voting')

OCRHypothesis = models_mod.OCRHypothesis
weighted_levenshtein = vote_mod.weighted_levenshtein
normalized_edit_distance = vote_mod.normalized_edit_distance
MultiFramePlateVoter = vote_mod.MultiFramePlateVoter


def test_weighted_levenshtein_confusion_discount():
    dist_reg = weighted_levenshtein('ABC', 'ADC')
    assert dist_reg == 1.0

    dist_conf = weighted_levenshtein('GJO1AB1234', 'GJ01AB1234')
    assert dist_conf < 0.50


def test_voting_unanimous_consensus():
    voter = MultiFramePlateVoter()
    hyps = [
        OCRHypothesis('cam1', 1, 1, 0.0, 'GJ01AB1234', 'GJ01AB1234', 0.90, 0.8, 1.0),
        OCRHypothesis('cam1', 1, 1, 150.0, 'GJ01AB1234', 'GJ01AB1234', 0.95, 0.8, 1.0),
        OCRHypothesis('cam1', 1, 1, 300.0, 'GJ01AB1234', 'GJ01AB1234', 0.92, 0.8, 1.0),
    ]
    res = voter.vote(hyps)
    assert res.is_resolved is True
    assert res.best_text == 'GJ01AB1234'
    assert res.support_count == 3
    assert res.confidence >= 0.85


def test_voting_filters_noisy_frame():
    voter = MultiFramePlateVoter()
    hyps = [
        OCRHypothesis('cam1', 2, 1, 0.0, 'GJ01AB1234', 'GJ01AB1234', 0.92, 0.85, 1.0),
        OCRHypothesis('cam1', 2, 1, 150.0, 'GJ01AB1234', 'GJ01AB1234', 0.94, 0.85, 1.0),
        OCRHypothesis('cam1', 2, 1, 300.0, 'GJO1AB1234', 'GJO1AB1234', 0.70, 0.60, 0.8),
        OCRHypothesis('cam1', 2, 1, 450.0, 'NOISY_STR', 'NOISYSTR', 0.30, 0.30, 0.2),
    ]
    res = voter.vote(hyps)
    assert res.is_resolved is True
    assert res.best_text == 'GJ01AB1234'
    assert res.support_count >= 2


def test_voting_low_confidence_fallback():
    voter = MultiFramePlateVoter()
    hyps = [
        OCRHypothesis('cam1', 3, 1, 0.0, 'X9', 'X9', 0.20, 0.15, 0.1),
    ]
    res = voter.vote(hyps)
    assert res.is_resolved is False
    assert res.status in ('LOW_CONFIDENCE', 'INSUFFICIENT_EVIDENCE')
