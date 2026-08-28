import time
import threading
from typing import Dict, List, Tuple
from .config import get_security_config


class LoginRateLimiter:
    """
    In-memory sliding-window login rate limiter to protect against brute force
    and credential stuffing while avoiding permanent denial of service.
    """

    def __init__(
        self,
        max_attempts: int | None = None,
        window_seconds: int | None = None,
        lockout_seconds: int | None = None
    ):
        cfg = get_security_config()
        self.max_attempts = max_attempts or cfg.rate_limit_max_attempts
        self.window_seconds = window_seconds or cfg.rate_limit_window_seconds
        self.lockout_seconds = lockout_seconds or cfg.rate_limit_lockout_seconds
        self._lock = threading.Lock()
        # Key -> list of timestamps
        self._attempts: Dict[str, List[float]] = {}
        # Key -> lockout expiry timestamp
        self._lockouts: Dict[str, float] = {}

    def is_allowed(self, key: str) -> Tuple[bool, int]:
        """
        Checks whether the key is currently allowed to attempt authentication.
        Returns (is_allowed, retry_after_seconds).
        """
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

            if len(timestamps) >= self.max_attempts:
                # Trigger temporary lockout
                self._lockouts[key] = now + self.lockout_seconds
                return False, self.lockout_seconds

            return True, 0

    def record_failure(self, key: str) -> Tuple[bool, int]:
        """
        Records a failed attempt for the key.
        Returns (is_locked_now, retry_after_seconds).
        """
        now = time.time()
        with self._lock:
            cutoff = now - self.window_seconds
            timestamps = [t for t in self._attempts.get(key, []) if t > cutoff]
            timestamps.append(now)
            self._attempts[key] = timestamps

            if len(timestamps) >= self.max_attempts:
                self._lockouts[key] = now + self.lockout_seconds
                return True, self.lockout_seconds

            return False, 0

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
