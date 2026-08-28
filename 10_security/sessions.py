import secrets
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from .models import Session, User, AuthenticatedPrincipal
from .repository import BaseSecurityRepository, get_security_repository
from .config import SecurityConfig, get_security_config
from .csrf import generate_csrf_token, hash_csrf_token
from .permissions import get_permissions_for_role


def hash_session_token(token: str) -> str:
    """Computes SHA-256 digest of a session token for secure server-side storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionManager:
    """Manages high-entropy opaque server-side sessions."""

    def __init__(
        self,
        repository: Optional[BaseSecurityRepository] = None,
        config: Optional[SecurityConfig] = None
    ):
        self.repo = repository or get_security_repository()
        self.config = config or get_security_config()

    def create_session(
        self,
        user: User,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[Session, str, str]:
        """
        Creates a new server-side session.
        Returns (SessionEntity, raw_session_token, raw_csrf_token).
        Raw tokens are sent to browser; only hashes are stored in database.
        """
        now = datetime.now(timezone.utc)
        raw_session_token = secrets.token_urlsafe(32)
        raw_csrf_token = generate_csrf_token()

        session_token_hash = hash_session_token(raw_session_token)
        csrf_token_hash = hash_csrf_token(raw_csrf_token)

        user_agent_hash = (
            hashlib.sha256(user_agent.encode("utf-8")).hexdigest()
            if user_agent
            else None
        )

        idle_expires_at = now + timedelta(seconds=self.config.session_idle_timeout_seconds)
        absolute_expires_at = now + timedelta(seconds=self.config.session_absolute_timeout_seconds)

        session = Session(
            session_id=str(uuid.uuid4()),
            session_token_hash=session_token_hash,
            user_id=user.user_id,
            created_at=now,
            last_seen_at=now,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
            csrf_token_hash=csrf_token_hash,
            source_ip=source_ip,
            user_agent_hash=user_agent_hash
        )

        self.repo.save_session(session)
        return session, raw_session_token, raw_csrf_token

    def validate_session(self, raw_session_token: str) -> Optional[Tuple[Session, User, AuthenticatedPrincipal]]:
        """
        Validates an incoming session token.
        If valid and active, extends idle timeout and returns (Session, User, Principal).
        If expired, revoked, or user disabled, returns None.
        """
        if not raw_session_token or len(raw_session_token) < 16:
            return None

        token_hash = hash_session_token(raw_session_token)
        session = self.repo.get_session_by_token_hash(token_hash)
        if not session or not session.is_active:
            return None

        user = self.repo.get_user_by_id(session.user_id)
        if not user or not user.enabled:
            return None

        now = datetime.now(timezone.utc)

        # Extend idle timeout if at least 60 seconds have elapsed since last write
        if (now - session.last_seen_at).total_seconds() > 60:
            new_idle_expiry = now + timedelta(seconds=self.config.session_idle_timeout_seconds)
            # Ensure idle expiry never extends past absolute expiry
            if new_idle_expiry > session.absolute_expires_at:
                new_idle_expiry = session.absolute_expires_at
            
            session.last_seen_at = now
            session.idle_expires_at = new_idle_expiry
            self.repo.update_session_activity(session.session_id, now, new_idle_expiry)

        permissions = get_permissions_for_role(user.role)
        principal = AuthenticatedPrincipal(
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            permissions=permissions,
            session_id=session.session_id,
            must_change_password=user.must_change_password
        )

        return session, user, principal

    def revoke_session_by_token(self, raw_session_token: str) -> bool:
        """Revokes a session by its raw token (e.g. upon logout)."""
        if not raw_session_token:
            return False
        token_hash = hash_session_token(raw_session_token)
        session = self.repo.get_session_by_token_hash(token_hash)
        if session:
            self.repo.revoke_session(session.session_id)
            return True
        return False

    def revoke_session_by_id(self, session_id: str) -> None:
        """Revokes a session by its session ID."""
        self.repo.revoke_session(session_id)

    def revoke_all_user_sessions(self, user_id: str) -> int:
        """Revokes all active sessions for a user (e.g. on role change, disable, password reset)."""
        return self.repo.revoke_all_user_sessions(user_id)

    def cleanup_expired(self) -> int:
        """Purges expired and revoked sessions."""
        return self.repo.cleanup_expired_sessions()


_GLOBAL_SESSION_MANAGER: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _GLOBAL_SESSION_MANAGER
    if _GLOBAL_SESSION_MANAGER is None:
        _GLOBAL_SESSION_MANAGER = SessionManager()
    return _GLOBAL_SESSION_MANAGER


def set_session_manager(manager: Optional[SessionManager]) -> None:
    global _GLOBAL_SESSION_MANAGER
    _GLOBAL_SESSION_MANAGER = manager


