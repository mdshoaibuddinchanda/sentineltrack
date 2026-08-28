import time
import threading
from typing import Dict, List, Tuple
from .config import get_security_config


class LoginRateLimiter:
    """
    In-memory sliding-window dual-tier login rate limiter to protect against:
    1. Targeted brute-force attacks (strict per-account/IP threshold).
    2. Password spraying across many usernames from a single source IP (aggregate IP threshold).
    """

    def __init__(
        self,
        max_attempts: int | None = None,
        max_ip_attempts: int | None = None,
        window_seconds: int | None = None,
        lockout_seconds: int | None = None
    ):
        cfg = get_security_config()
        self.max_attempts = max_attempts or cfg.rate_limit_max_attempts
        self.max_ip_attempts = max_ip_attempts or getattr(cfg, "rate_limit_max_ip_attempts", 30)
        self.window_seconds = window_seconds or cfg.rate_limit_window_seconds
        self.lockout_seconds = lockout_seconds or cfg.rate_limit_lockout_seconds
        self._lock = threading.Lock()
        # Key -> list of timestamps
        self._attempts: Dict[str, List[float]] = {}
        # Key -> lockout expiry timestamp
        self._lockouts: Dict[str, float] = {}

    def is_allowed(self, key: str, max_attempts: int | None = None) -> Tuple[bool, int]:
        """
        Checks whether a generic key is currently allowed.
        Returns (is_allowed, retry_after_seconds).
        """
        limit = max_attempts or self.max_attempts
        now = time.time()
        with self._lock:
            # Check active lockout
            if key in self._lockouts:
                expiry = self._lockouts[key]
                if now < expiry:
                    retry_after = max(1, int(expiry - now))
                    return False, retry_after
                else:
                    # Lockout expired
                    del self._lockouts[key]
                    self._attempts[key] = []

            # Prune attempts outside window
            cutoff = now - self.window_seconds
            timestamps = [t for t in self._attempts.get(key, []) if t > cutoff]
            self._attempts[key] = timestamps

            if len(timestamps) >= limit:
                # Trigger temporary lockout
                self._lockouts[key] = now + self.lockout_seconds
                return False, self.lockout_seconds

            return True, 0

    def record_failure(self, key: str, max_attempts: int | None = None) -> Tuple[bool, int]:
        """
        Records a failed attempt for a generic key.
        Returns (is_locked_now, retry_after_seconds).
        """
        limit = max_attempts or self.max_attempts
        now = time.time()
        with self._lock:
            cutoff = now - self.window_seconds
            timestamps = [t for t in self._attempts.get(key, []) if t > cutoff]
            timestamps.append(now)
            self._attempts[key] = timestamps

            if len(timestamps) >= limit:
                self._lockouts[key] = now + self.lockout_seconds
                return True, self.lockout_seconds

            return False, 0

    def check_login_allowed(self, username: str, client_ip: str) -> Tuple[bool, int]:
        """
        Dual-tier rate check:
        1. Account tier: acct:{client_ip}:{username} (strict threshold against targeted brute-force)
        2. Source IP tier: ip:{client_ip} (aggregate threshold against password spraying)
        """
        acct_key = f"acct:{client_ip}:{username.strip().lower()}"
        ip_key = f"ip:{client_ip}"

        acct_allowed, acct_retry = self.is_allowed(acct_key, max_attempts=self.max_attempts)
        if not acct_allowed:
            return False, acct_retry

        ip_allowed, ip_retry = self.is_allowed(ip_key, max_attempts=self.max_ip_attempts)
        if not ip_allowed:
            return False, ip_retry

        return True, 0

    def record_login_failure(self, username: str, client_ip: str) -> Tuple[bool, int]:
        """
        Records failure against both the specific account key and the aggregate source IP key.
        """
        acct_key = f"acct:{client_ip}:{username.strip().lower()}"
        ip_key = f"ip:{client_ip}"

        acct_locked, acct_retry = self.record_failure(acct_key, max_attempts=self.max_attempts)
        ip_locked, ip_retry = self.record_failure(ip_key, max_attempts=self.max_ip_attempts)

        if acct_locked:
            return True, acct_retry
        if ip_locked:
            return True, ip_retry
        return False, 0

    def record_login_success(self, username: str, client_ip: str) -> None:
        """
        Clears account-specific failures on successful login.
        """
        acct_key = f"acct:{client_ip}:{username.strip().lower()}"
        self.record_success(acct_key)

    def record_success(self, key: str) -> None:
        """Clears failed attempts upon successful authentication."""
        with self._lock:
            self._attempts.pop(key, None)
            self._lockouts.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._attempts = {}
            self._lockouts = {}



_GLOBAL_RATE_LIMITER: LoginRateLimiter | None = None


def get_login_rate_limiter() -> LoginRateLimiter:
    global _GLOBAL_RATE_LIMITER
    if _GLOBAL_RATE_LIMITER is None:
        _GLOBAL_RATE_LIMITER = LoginRateLimiter()
    return _GLOBAL_RATE_LIMITER
