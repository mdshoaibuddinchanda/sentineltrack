import os
from dataclasses import dataclass, field
from typing import List, Optional



@dataclass
class SecurityConfig:
    """Security configuration for SentinelTrack."""
    env: str = field(default_factory=lambda: os.getenv("SENTINEL_ENV", "development").lower())
    
    # Session & Cookie
    session_idle_timeout_seconds: int = 1800      # 30 minutes
    session_absolute_timeout_seconds: int = 28800  # 8 hours
    cookie_name: str = "sentinel_session"
    cookie_samesite: str = "strict"
    cookie_path: str = "/"
    cookie_secure: bool = False                    # Enabled in production or via env
    
    # Password Policy & Argon2id
    password_min_length: int = 15
    password_max_length: int = 128
    argon2_time_cost: int = 2
    argon2_memory_cost_kib: int = 19456           # 19 MiB OWASP recommended minimum
    argon2_parallelism: int = 1
    
    # Rate Limiting (Login Abuse Resistance)
    rate_limit_max_attempts: int = 5
    rate_limit_window_seconds: int = 60
    rate_limit_lockout_seconds: int = 120
    
    # CORS & Origins
    allowed_origins: List[str] = field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    
    # Audit Logging
    audit_page_size_default: int = 50
    audit_page_size_max: int = 500

    def __post_init__(self):
        # In production mode, force cookie_secure to True unless explicitly overridden
        if self.env == "production":
            self.cookie_secure = True
        elif os.getenv("SENTINEL_COOKIE_SECURE", "").lower() in ("true", "1", "yes"):
            self.cookie_secure = True

        custom_origins = os.getenv("SENTINEL_ALLOWED_ORIGINS")
        if custom_origins:
            self.allowed_origins = [o.strip() for o in custom_origins.split(",") if o.strip()]


_GLOBAL_SECURITY_CONFIG: SecurityConfig | None = None


def get_security_config() -> SecurityConfig:
    global _GLOBAL_SECURITY_CONFIG
    if _GLOBAL_SECURITY_CONFIG is None:
        _GLOBAL_SECURITY_CONFIG = SecurityConfig()
    return _GLOBAL_SECURITY_CONFIG


def set_security_config(cfg: Optional[SecurityConfig] = None) -> None:
    global _GLOBAL_SECURITY_CONFIG
    _GLOBAL_SECURITY_CONFIG = cfg

