import importlib

gram_mod = importlib.import_module('04_plate_ocr.grammar')
score_indian_grammar = gram_mod.score_indian_grammar
generate_grammar_alternatives = gram_mod.generate_grammar_alternatives
is_plausible_indian_registration_evidence = gram_mod.is_plausible_indian_registration_evidence
is_complete_indian_registration_evidence = gram_mod.is_complete_indian_registration_evidence


def test_standard_indian_grammar_scoring():
    assert score_indian_grammar('GJ01AB1234') >= 0.95
    assert score_indian_grammar('MH12DE1432') >= 0.95
    assert score_indian_grammar('DL8CAF1234') >= 0.95
    assert score_indian_grammar('KA05N9999') >= 0.95


def test_bh_series_grammar_scoring():
    assert score_indian_grammar('22BH1234AA') >= 0.90
    assert score_indian_grammar('23BH5678B') >= 0.90


def test_soft_grammar_continuity():
    sc_custom = score_indian_grammar('GJ1A1234')
    assert 0.40 <= sc_custom <= 1.0

    sc_gibberish = score_indian_grammar('ZZ99ZZ9999')
    assert 0.0 < sc_gibberish < 0.80


def test_grammar_positional_alternatives():
    alts = generate_grammar_alternatives('GJO1AB1234')
    alt_strings = [a[0] for a in alts]
    assert 'GJ01AB1234' in alt_strings


def test_signage_and_short_noise_are_not_registration_evidence():
    for text in ("GSRTC", "WEKARE", "SHVAS", "EETEK", "SEEVA", "EOFAHA", "5PREA", "9EE03", "WELCOME123", "WE12AB3456"):
        assert is_plausible_indian_registration_evidence(text) is False

    assert is_plausible_indian_registration_evidence("GJ01AB1234") is True
    assert is_plausible_indian_registration_evidence("J01AB1234") is True


def test_complete_and_partial_registration_evidence_are_distinct():
    assert is_complete_indian_registration_evidence("GJ01AB1234") is True
    assert is_complete_indian_registration_evidence("AB1234") is False
    assert is_plausible_indian_registration_evidence("AB1234") is True
    assert is_plausible_indian_registration_evidence("01AB1234") is True
    assert is_plausible_indian_registration_evidence("GJAB1234") is True
