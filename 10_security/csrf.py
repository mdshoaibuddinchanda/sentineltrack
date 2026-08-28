import secrets
import hashlib
import hmac


def generate_csrf_token() -> str:
    """Generates a cryptographically secure 256-bit CSRF synchronizer token."""
    return secrets.token_urlsafe(32)


def hash_csrf_token(token: str) -> str:
    """Computes SHA-256 digest of a CSRF token for secure server-side storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_csrf_token(submitted_token: str | None, stored_token_hash: str | None) -> bool:
    """Constant-time verification of a submitted CSRF token against stored token hash."""
    if not submitted_token or not stored_token_hash:
        return False
    computed_hash = hash_csrf_token(submitted_token)
    return hmac.compare_digest(computed_hash, stored_token_hash)
