import sys
import pytest
import importlib

sys.path.insert(0, 'c:/DR2/sentineltrack')
_pw = importlib.import_module('10_security.password')
PasswordPolicy = _pw.PasswordPolicy
hash_password = _pw.hash_password
verify_password = _pw.verify_password


class TestPasswordPolicyValidate:
    def test_password_too_short(self):
        with pytest.raises(ValueError):
            hash_password('short')

    def test_password_at_min_length(self):
        pw = 'A' * 15
        ok, msg = PasswordPolicy.validate(pw)
        assert ok is True
        assert msg == ''

    def test_password_64_chars(self):
        pw = 'B' * 64
        ok, msg = PasswordPolicy.validate(pw)
        assert ok is True

    def test_password_empty(self):
        ok, msg = PasswordPolicy.validate('')
        assert ok is False
        assert len(msg) > 0

    def test_password_too_short_validate(self):
        ok, msg = PasswordPolicy.validate('12345678901234')
        assert ok is False
        assert '15' in msg


class TestHashAndVerify:
    def test_hash_and_verify_roundtrip(self):
        pw = 'CorrectHorseBatteryStaple2026!'
        h = hash_password(pw)
        assert verify_password(pw, h) is True

    def test_wrong_password_fails(self):
        pw = 'CorrectHorseBatteryStaple2026!'
        h = hash_password(pw)
        assert verify_password('WrongPasswordXYZ!', h) is False

    def test_different_hashes_for_same_password(self):
        pw = 'SamePasswordEveryTime123!'
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        assert h1 != h2

    def test_hash_is_argon2id(self):
        pw = 'SecurityTestPassword2026'
        h = hash_password(pw)
        assert h.startswith('$argon2id$')

