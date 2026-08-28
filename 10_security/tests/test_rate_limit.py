import pytest
import importlib

_rate = importlib.import_module("10_security.rate_limit")
LoginRateLimiter = _rate.LoginRateLimiter


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
