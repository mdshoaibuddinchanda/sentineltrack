"""
SentinelTrack Priority 10 - Security, Authentication, RBAC, Sessions & Audit Module
"""
try:
    from .models import UserRole, Permission, User, Session, AuthenticatedPrincipal, AuditEvent
    from .permissions import ROLE_PERMISSIONS, has_permission
    from .password import PasswordPolicy, hash_password, verify_password
    from .csrf import generate_csrf_token, verify_csrf_token
    from .sessions import SessionManager, get_session_manager
    from .audit import AuditLogger, get_audit_logger
    from .repository import get_security_repository
    from .config import SecurityConfig, get_security_config
except (ImportError, ValueError):
    import importlib
    _mod = importlib.import_module("10_security.models")
    UserRole, Permission, User, Session, AuthenticatedPrincipal, AuditEvent = (
        _mod.UserRole, _mod.Permission, _mod.User, _mod.Session, _mod.AuthenticatedPrincipal, _mod.AuditEvent
    )
    _perm = importlib.import_module("10_security.permissions")
    ROLE_PERMISSIONS, has_permission = _perm.ROLE_PERMISSIONS, _perm.has_permission
    _pw = importlib.import_module("10_security.password")
    PasswordPolicy, hash_password, verify_password = _pw.PasswordPolicy, _pw.hash_password, _pw.verify_password
    _csrf = importlib.import_module("10_security.csrf")
    generate_csrf_token, verify_csrf_token = _csrf.generate_csrf_token, _csrf.verify_csrf_token
    _sess = importlib.import_module("10_security.sessions")
    SessionManager, get_session_manager = _sess.SessionManager, _sess.get_session_manager
    _aud = importlib.import_module("10_security.audit")
    AuditLogger, get_audit_logger = _aud.AuditLogger, _aud.get_audit_logger
    _repo = importlib.import_module("10_security.repository")
    get_security_repository = _repo.get_security_repository
    _cfg = importlib.import_module("10_security.config")
    SecurityConfig, get_security_config = _cfg.SecurityConfig, _cfg.get_security_config

__all__ = [
    "UserRole",
    "Permission",
    "User",
    "Session",
    "AuthenticatedPrincipal",
    "AuditEvent",
    "ROLE_PERMISSIONS",
    "has_permission",
    "PasswordPolicy",
    "hash_password",
    "verify_password",
    "generate_csrf_token",
    "verify_csrf_token",
    "SessionManager",
    "get_session_manager",
    "AuditLogger",
    "get_audit_logger",
    "get_security_repository",
    "SecurityConfig",
    "get_security_config",
]


