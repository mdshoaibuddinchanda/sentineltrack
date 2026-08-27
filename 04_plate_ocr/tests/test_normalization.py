import importlib

norm_mod = importlib.import_module('04_plate_ocr.normalization')
normalize_plate_text = norm_mod.normalize_plate_text
is_valid_candidate_length = norm_mod.is_valid_candidate_length


def test_normalization_whitespace_and_casing():
    assert normalize_plate_text('  gj 01 ab 1234  ') == 'GJ01AB1234'
    assert normalize_plate_text('mh-12-de-1432') == 'MH12DE1432'


def test_normalization_punctuation_and_separators():
    assert normalize_plate_text('DL.8CAF.1234') == 'DL8CAF1234'
    assert normalize_plate_text('UP_32:AA/0001') == 'UP32AA0001'


def test_normalization_does_not_globally_replace_letters():
    # Crucial test: Ensure O is NOT globally mapped to 0 (preserves state code / series letters)
    assert normalize_plate_text('OD02AB1234') == 'OD02AB1234'
    assert normalize_plate_text('GJ01AO1234') == 'GJ01AO1234'
    # Ensure B is NOT globally mapped to 8
    assert normalize_plate_text('BR01AB1234') == 'BR01AB1234'


def test_valid_candidate_length():
    assert is_valid_candidate_length('GJ01AB1234') is True
    assert is_valid_candidate_length('22BH1234AA') is True
    assert is_valid_candidate_length('ABC') is False
    assert is_valid_candidate_length('VERYLONGINVALIDREGISTRATIONSTRING') is False
