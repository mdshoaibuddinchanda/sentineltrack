import pytest
import importlib
from datetime import datetime, timezone, timedelta

_sec = importlib.import_module("10_security")
User = _sec.User
UserRole = _sec.UserRole
SecurityConfig = _sec.SecurityConfig
_repo_mod = importlib.import_module("10_security.repository")
SqliteSecurityRepository = _repo_mod.SqliteSecurityRepository
_sess_mod = importlib.import_module("10_security.sessions")
SessionManager = _sess_mod.SessionManager


@pytest.fixture
def repo():
    return SqliteSecurityRepository(":memory:")


@pytest.fixture
def user(repo):
    u = User(
        user_id="user-123",
        username="operator1",
        display_name="Operator One",
        password_hash="$argon2id$mockhash",
        role=UserRole.OPERATOR,
        enabled=True
    )
    repo.save_user(u)
    return u


class TestSessionManager:
    def test_create_and_validate_session(self, repo, user):
        mgr = SessionManager(repository=repo)
        session, raw_token, csrf_token = mgr.create_session(user, source_ip="127.0.0.1")

        assert isinstance(raw_token, str)
        assert len(raw_token) >= 32
        assert isinstance(csrf_token, str)
        assert len(csrf_token) >= 32

        result = mgr.validate_session(raw_token)
        assert result is not None
        valid_sess, valid_user, principal = result
        assert valid_sess.session_id == session.session_id
        assert valid_user.user_id == user.user_id
        assert principal.username == user.username
        assert principal.role == UserRole.OPERATOR

    def test_validate_invalid_token(self, repo):
        mgr = SessionManager(repository=repo)
        assert mgr.validate_session("invalid-token-that-does-not-exist") is None
        assert mgr.validate_session("") is None
        assert mgr.validate_session(None) is None

    def test_revoke_session_by_token(self, repo, user):
        mgr = SessionManager(repository=repo)
        session, raw_token, _ = mgr.create_session(user)

        assert mgr.validate_session(raw_token) is not None
        revoked = mgr.revoke_session_by_token(raw_token)
        assert revoked is True

        assert mgr.validate_session(raw_token) is None

    def test_revoke_all_user_sessions(self, repo, user):
        mgr = SessionManager(repository=repo)
        _, raw_token1, _ = mgr.create_session(user)
        _, raw_token2, _ = mgr.create_session(user)

        assert mgr.validate_session(raw_token1) is not None
        assert mgr.validate_session(raw_token2) is not None

        count = mgr.revoke_all_user_sessions(user.user_id)
        assert count == 2

        assert mgr.validate_session(raw_token1) is None
        assert mgr.validate_session(raw_token2) is None

    def test_disabled_user_cannot_validate_session(self, repo, user):
        mgr = SessionManager(repository=repo)
        _, raw_token, _ = mgr.create_session(user)

        user.enabled = False
        repo.update_user(user)

        assert mgr.validate_session(raw_token) is None

    def test_expired_session_cannot_validate(self, repo, user):
        mgr = SessionManager(repository=repo)
        session, raw_token, _ = mgr.create_session(user)

        # Manually expire the session in repo
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        session.idle_expires_at = past
        repo.save_session(session)

        assert mgr.validate_session(raw_token) is None

