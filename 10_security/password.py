import time
from typing import Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from .config import get_security_config


def get_password_hasher() -> PasswordHasher:
    cfg = get_security_config()
    return PasswordHasher(
        time_cost=cfg.argon2_time_cost,
        memory_cost=cfg.argon2_memory_cost_kib,
        parallelism=cfg.argon2_parallelism,
        hash_len=32,
        salt_len=16,
    )


class PasswordPolicy:
    """Password validation policy enforcing length without restrictive composition."""

    @staticmethod
    def validate(password: str) -> Tuple[bool, str]:
        cfg = get_security_config()
        if not password or len(password) < cfg.password_min_length:
            return False, f"Password must be at least {cfg.password_min_length} characters long."
        if len(password) > cfg.password_max_length:
            return False, f"Password must not exceed {cfg.password_max_length} characters."
        return True, ""


def hash_password(password: str) -> str:
    """Hashes a password using Argon2id."""
    valid, err_msg = PasswordPolicy.validate(password)
    if not valid:
        raise ValueError(err_msg)
    
    hasher = get_password_hasher()
    return hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifies a password against an Argon2id hash."""
    if not password or not password_hash:
        return False
    hasher = get_password_hasher()
    try:
        return hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# Pre-computed dummy Argon2id hash for constant-time authentication timing equalization
_dummy_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, hash_len=32, salt_len=16)
DUMMY_PASSWORD_HASH = _dummy_hasher.hash("DummyConstantTimingAuthPassword123!")



def benchmark_argon2_latency(iterations: int = 5) -> float:
    """Measures local Argon2id hashing latency in milliseconds."""
    test_pwd = "A secure multi-word police passphrase 2026!"
    hasher = get_password_hasher()
    
    # Warmup
    hasher.hash("warmup-password-string-12345")
    
    start = time.perf_counter()
    for _ in range(iterations):
        h = hasher.hash(test_pwd)
        hasher.verify(h, test_pwd)
    elapsed = time.perf_counter() - start
    
    return (elapsed / (iterations * 2)) * 1000.0
