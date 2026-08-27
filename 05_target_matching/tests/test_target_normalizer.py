import importlib

norm_mod = importlib.import_module('05_target_matching.normalizer')
normalize_target_registration = norm_mod.normalize_target_registration
normalize_search_query = norm_mod.normalize_search_query


def test_target_normalization_clean_input():
    norm, valid, err = normalize_target_registration('GJ-01-AB-1234')
    assert valid is True
    assert norm == 'GJ01AB1234'
    assert err is None


def test_target_normalization_whitespace_and_casing():
    norm, valid, err = normalize_target_registration('  mh 12 de 1432   ')
    assert valid is True
    assert norm == 'MH12DE1432'


def test_target_normalization_rejects_empty():
    norm, valid, err = normalize_target_registration('')
    assert valid is False
    assert 'empty' in err.lower()


def test_target_normalization_rejects_too_short():
    norm, valid, err = normalize_target_registration('AB')
    assert valid is False
    assert 'too short' in err.lower()


def test_normalize_search_query_wildcards():
    query, is_wild, valid = normalize_search_query('GJ01AB*')
    assert valid is True
    assert is_wild is True
    assert query == 'GJ01AB*'
