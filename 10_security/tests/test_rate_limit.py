import sys
from pathlib import Path
import pytest
import importlib
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_rate = importlib.import_module("10_security.rate_limit")
LoginRateLimiter = _rate.LoginRateLimiter
_backend = importlib.import_module("08_backend.app")
_sec_repo = importlib.import_module("10_security.repository")
_sec_sess = importlib.import_module("10_security.sessions")
_sec_pw = importlib.import_module("10_security.password")
_sec_models = importlib.import_module("10_security.models")


class TestRateLimiter:
    def test_first_attempt_allowed(self):
        limiter = LoginRateLimiter(max_attempts=3, window_seconds=60, lockout_seconds=300)
        allowed, retry_after = limiter.is_allowed("user1:127.0.0.1")
        assert allowed is True
        assert retry_after == 0

    def test_lockout_after_max_attempts(self):
        limiter = LoginRateLimiter(max_attempts=3, window_seconds=60, lockout_seconds=300)
        key = "user2:127.0.0.1"

        # Record 3 failures
        for _ in range(3):
            limiter.record_failure(key)

        allowed, retry_after = limiter.is_allowed(key)
        assert allowed is False
        assert retry_after > 0

    def test_different_keys_independent(self):
        limiter = LoginRateLimiter(max_attempts=2, window_seconds=60, lockout_seconds=300)
        key1 = "userA:1.1.1.1"
        key2 = "userB:1.1.1.1"

        limiter.record_failure(key1)
        limiter.record_failure(key1)

        # key1 locked out
        assert limiter.is_allowed(key1)[0] is False
        # key2 still allowed
        assert limiter.is_allowed(key2)[0] is True

    def test_successful_login_resets_failures(self):
        limiter = LoginRateLimiter(max_attempts=3, window_seconds=60, lockout_seconds=300)
        key = "user3:127.0.0.1"

        limiter.record_failure(key)
        limiter.record_failure(key)
        limiter.record_success(key)

        assert limiter.is_allowed(key)[0] is True
        # Should be able to fail 2 more times without lockout
        limiter.record_failure(key)
        assert limiter.is_allowed(key)[0] is True

    def test_password_spray_aggregate_ip_lockout(self):
        """
        Password Spray Defense:
        An attacker making 1 attempt against 40 different usernames from the same source IP
        is blocked once the aggregate source IP threshold (max_ip_attempts=30) is reached.
        """
        limiter = LoginRateLimiter(
            max_attempts=5,
            max_ip_attempts=30,
            window_seconds=60,
            lockout_seconds=300
        )
        source_ip = "198.51.100.5"

        # First 30 attempts across distinct usernames are permitted but recorded
        for i in range(30):
            username = f"target_user_{i:03d}"
            allowed, _ = limiter.check_login_allowed(username, source_ip)
            assert allowed is True, f"Attempt {i+1} should be allowed"
            limiter.record_login_failure(username, source_ip)

        # 31st attempt against a brand-new username from same IP is locked out
        new_username = "target_user_031"
        allowed, retry_after = limiter.check_login_allowed(new_username, source_ip)
        assert allowed is False
        assert retry_after > 0

        # A different source IP is not affected
        allowed_other, _ = limiter.check_login_allowed(new_username, "198.51.100.99")
        assert allowed_other is True

    def test_dual_tier_account_lockout(self):
        """Targeted Brute-Force: 5 failed attempts against the same username triggers account lockout."""
        limiter = LoginRateLimiter(
            max_attempts=5,
            max_ip_attempts=30,
            window_seconds=60,
            lockout_seconds=300
        )
        source_ip = "198.51.100.10"
        target_username = "victim_operator"

        for i in range(5):
            allowed, _ = limiter.check_login_allowed(target_username, source_ip)
            assert allowed is True
            limiter.record_login_failure(target_username, source_ip)

        # 6th attempt against same username is locked out
        allowed, retry_after = limiter.check_login_allowed(target_username, source_ip)
        assert allowed is False
        assert retry_after > 0

