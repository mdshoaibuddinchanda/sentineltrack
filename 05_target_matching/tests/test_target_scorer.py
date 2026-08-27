import importlib

scorer_mod = importlib.import_module('05_target_matching.scorer')
models_mod = importlib.import_module('05_target_matching.models')
TargetMatchScorer = scorer_mod.TargetMatchScorer
MatchClass = models_mod.MatchClass


def test_scorer_exact_match_fast_path():
    scorer = TargetMatchScorer()
    res = scorer.score_match(
        target_id='tgt-001',
        target_registration='GJ01AB1234',
        observed_registration='GJ01AB1234',
        multi_frame_support=3
    )
    assert res.match_class == MatchClass.EXACT
    assert res.match_score == 1.0
    assert res.exact_match is True
    assert len(res.reasons) > 0


def test_scorer_high_probability_plausible_confusion():
    scorer = TargetMatchScorer()
    # 1 OCR confusion (B -> 8) with high OCR confidence and 3 frame support
    res = scorer.score_match(
        target_id='tgt-001',
        target_registration='GJ01AB1234',
        observed_registration='GJ01A81234',
        ocr_confidence=0.92,
        multi_frame_support=3,
        total_hypotheses=3
    )
    assert res.match_score >= 0.85
    assert res.match_class == MatchClass.HIGH_PROBABILITY
    assert any('Position' in r for r in res.reasons)


def test_scorer_rejected_for_unrelated_plate():
    scorer = TargetMatchScorer()
    res = scorer.score_match(
        target_id='tgt-001',
        target_registration='GJ01AB1234',
        observed_registration='DL04XY9999',
        ocr_confidence=0.90,
        multi_frame_support=2
    )
    assert res.match_score < 0.50
    assert res.match_class == MatchClass.REJECTED


def test_scorer_single_frame_penalty():
    scorer = TargetMatchScorer()
    # Identical features except support count
    res_multi = scorer.score_match(
        target_id='tgt-001',
        target_registration='GJ01AB1234',
        observed_registration='GJ01A81234',
        multi_frame_support=3
    )
    res_single = scorer.score_match(
        target_id='tgt-001',
        target_registration='GJ01AB1234',
        observed_registration='GJ01A81234',
        multi_frame_support=1
    )
    assert res_multi.match_score > res_single.match_score
