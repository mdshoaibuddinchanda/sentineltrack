import pytest
import importlib
from datetime import datetime, timezone, timedelta

_sec = importlib.import_module("10_security")
User = _sec.User
UserRole = _sec.UserRole
Session = _sec.Session
AuditEvent = _sec.AuditEvent
_repo_mod = importlib.import_module("10_security.repository")
SqliteSecurityRepository = _repo_mod.SqliteSecurityRepository


@pytest.fixture
def repo():
    return SqliteSecurityRepository(":memory:")


class TestSqliteSecurityRepository:
    def test_user_crud(self, repo):
        user = User(
            user_id="u1",
            username="admin_test",
            display_name="Admin Test",
            password_hash="$argon2id$testhash",
            role=UserRole.ADMIN,
            enabled=True
        )
        repo.save_user(user)

        fetched = repo.get_user_by_id("u1")
        assert fetched is not None
        assert fetched.username == "admin_test"
        assert fetched.role == UserRole.ADMIN

        by_uname = repo.get_user_by_username("admin_test")
        assert by_uname is not None
        assert by_uname.user_id == "u1"

        # Update user
        user.display_name = "Updated Admin"
        user.enabled = False
        repo.update_user(user)

        updated = repo.get_user_by_id("u1")
        assert updated.display_name == "Updated Admin"
        assert updated.enabled is False

    def test_count_and_list_users(self, repo):
        assert repo.count_users() == 0
        u1 = User("u1", "user1", "User 1", "hash", UserRole.OPERATOR)
        u2 = User("u2", "user2", "User 2", "hash", UserRole.ADMIN)
        repo.save_user(u1)
        repo.save_user(u2)

        assert repo.count_users() == 2
        assert repo.count_active_admins() == 1

        users = repo.list_users(limit=10, offset=0)
        assert len(users) == 2

    def test_session_lifecycle(self, repo):
        now = datetime.now(timezone.utc)
        sess = Session(
            session_id="s1",
            session_token_hash="tokenhash123",
            user_id="u1",
            created_at=now,
            last_seen_at=now,
            idle_expires_at=now + timedelta(hours=1),
            absolute_expires_at=now + timedelta(hours=8),
            csrf_token_hash="csrfhash123"
        )
        repo.save_session(sess)

        fetched = repo.get_session_by_token_hash("tokenhash123")
        assert fetched is not None
        assert fetched.session_id == "s1"
        assert fetched.is_active is True

        repo.revoke_session("s1")
        revoked = repo.get_session_by_token_hash("tokenhash123")
        assert revoked.is_active is False

    def test_audit_event_persistence_and_query(self, repo):
        now = datetime.now(timezone.utc)
        event = AuditEvent(
            audit_id="a1",
            event_time_utc=now,
            actor_user_id="u1",
            actor_username="admin1",
            actor_role="ADMIN",
            action="LOGIN_SUCCESS",
            resource_type="auth",
            resource_id=None,
            outcome="SUCCESS",
            details_json={"ip": "127.0.0.1"}
        )
        repo.save_audit_event(event)

        events = repo.query_audit_events(action="LOGIN_SUCCESS")
        assert len(events) == 1
        assert events[0].actor_username == "admin1"
        assert events[0].details_json == {"ip": "127.0.0.1"}

        assert repo.count_audit_events() == 1
        assert repo.count_audit_events(action="OTHER") == 0
