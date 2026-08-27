import importlib

dist_mod = importlib.import_module('05_target_matching.distance')
is_exact_match = dist_mod.is_exact_match
standard_levenshtein = dist_mod.standard_levenshtein
damerau_levenshtein = dist_mod.damerau_levenshtein
position_weighted_edit_distance = dist_mod.position_weighted_edit_distance
calculate_normalized_similarity = dist_mod.calculate_normalized_similarity


def test_exact_match():
    assert is_exact_match('GJ01AB1234', 'GJ01AB1234') is True
    assert is_exact_match('GJ01AB1234', 'GJ01AB1235') is False
    assert is_exact_match('', '') is False


def test_standard_levenshtein():
    assert standard_levenshtein('GJ01AB1234', 'GJ01AB1234') == 0
    assert standard_levenshtein('GJ01AB1234', 'GJ01AB1235') == 1
    assert standard_levenshtein('GJ01AB1234', 'GJ01AB12') == 2
    assert standard_levenshtein('GJ01AB1234', 'GJ01AB12345') == 1


def test_damerau_levenshtein_transposition():
    # Adjacent transposition AB -> BA is 1 edit in Damerau, but 2 in standard Levenshtein
    assert damerau_levenshtein('GJ01BA1234', 'GJ01AB1234') == 1
    assert standard_levenshtein('GJ01BA1234', 'GJ01AB1234') == 2


def test_position_aware_confusion_state_slot():
    # Slot 0: '0' observed instead of 'O' in 'OD01AB1234'
    # Should be heavily discounted (0.20) because slot 0 expects LETTERS
    dist, reasons = position_weighted_edit_distance('OD01AB1234', '0D01AB1234')
    assert dist == 0.20
    assert any('plausible OCR confusion' in r for r in reasons)


def test_position_aware_confusion_rto_slot():
    # Slot 2-3: 'O' observed instead of '0' in 'GJ01AB1234' -> 'GJO1AB1234'
    # Should be discounted (0.20) because slot 2 expects DIGITS
    dist, reasons = position_weighted_edit_distance('GJ01AB1234', 'GJO1AB1234')
    assert dist == 0.20


def test_position_aware_b8_confusion():
    # B vs 8 confusion in numeric suffix: 'GJ01AB1234' vs 'GJ01AB1238' (mismatch) vs 'GJ01A81234' (series B/8)
    dist, reasons = position_weighted_edit_distance('GJ01AB1234', 'GJ01A81234')
    assert dist <= 0.35


def test_inappropriate_substitution_costs_full_unit():
    # 'GJ01AB1234' vs 'GJ01AX1234' (B -> X is not a recognized confusion)
    dist, reasons = position_weighted_edit_distance('GJ01AB1234', 'GJ01AX1234')
    assert dist == 1.0


def test_normalized_similarity():
    sim_exact = calculate_normalized_similarity('GJ01AB1234', 'GJ01AB1234', 0.0)
    assert sim_exact == 1.0
    sim_close = calculate_normalized_similarity('GJ01AB1234', 'GJ01A81234', 0.20)
    assert sim_close >= 0.95
