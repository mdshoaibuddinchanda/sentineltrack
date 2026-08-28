import pytest
import importlib

_csrf = importlib.import_module("10_security.csrf")
generate_csrf_token = _csrf.generate_csrf_token
hash_csrf_token = _csrf.hash_csrf_token
verify_csrf_token = _csrf.verify_csrf_token


class TestCsrf:
    def test_token_is_str(self):
        tok = generate_csrf_token()
        assert isinstance(tok, str)
        assert len(tok) >= 32

    def test_tokens_unique(self):
        tok1 = generate_csrf_token()
        tok2 = generate_csrf_token()
        assert tok1 != tok2

    def test_verify_correct_token(self):
        tok = generate_csrf_token()
        h = hash_csrf_token(tok)
        assert verify_csrf_token(tok, h) is True

    def test_verify_wrong_token(self):
        tok1 = generate_csrf_token()
        tok2 = generate_csrf_token()
        h1 = hash_csrf_token(tok1)
        assert verify_csrf_token(tok2, h1) is False

    def test_verify_empty_token(self):
        tok = generate_csrf_token()
        h = hash_csrf_token(tok)
        assert verify_csrf_token("", h) is False
        assert verify_csrf_token(tok, "") is False

    def test_verify_none_token(self):
        tok = generate_csrf_token()
        h = hash_csrf_token(tok)
        assert verify_csrf_token(None, h) is False
        assert verify_csrf_token(tok, None) is False
