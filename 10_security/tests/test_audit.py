import pytest
import importlib

_sec = importlib.import_module("10_security")
UserRole = _sec.UserRole
AuthenticatedPrincipal = _sec.AuthenticatedPrincipal
_repo_mod = importlib.import_module("10_security.repository")
SqliteSecurityRepository = _repo_mod.SqliteSecurityRepository
_aud_mod = importlib.import_module("10_security.audit")
AuditLogger = _aud_mod.AuditLogger
sanitize_audit_string = _aud_mod.sanitize_audit_string
redact_sensitive_dict = _aud_mod.redact_sensitive_dict


@pytest.fixture
def repo():
    return SqliteSecurityRepository(":memory:")


@pytest.fixture
def logger(repo):
    return AuditLogger(repository=repo)


class TestAuditLogger:
    def test_sanitize_audit_string(self):
        dirty = "admin\n malicious\r\t injection"
        clean = sanitize_audit_string(dirty)
        assert "\n" not in clean
        assert "\r" not in clean
        assert "\t" not in clean
        assert "admin" in clean
        assert "malicious" in clean

    def test_redact_sensitive_dict(self):
        payload = {
            "username": "operator1",
            "password": "SuperSecretPassword123!",
            "token": "secret-session-token",
            "metadata": {
                "csrf_token": "csrf123",
                "normal_field": "visible_value"
            }
        }
        redacted = redact_sensitive_dict(payload)
        assert redacted["username"] == "operator1"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["token"] == "[REDACTED]"
        assert redacted["metadata"]["csrf_token"] == "[REDACTED]"
        assert redacted["metadata"]["normal_field"] == "visible_value"

    def test_log_event_with_principal(self, logger, repo):
        principal = AuthenticatedPrincipal(
            user_id="u1",
            username="admin_user",
            display_name="Admin",
            role=UserRole.ADMIN,
            permissions={"all"},
            session_id="s1"
        )
        logger.log_event(
            action="TARGET_CREATED",
            resource_type="target",
            resource_id="tgt-99",
            outcome="SUCCESS",
            principal=principal,
            details={"registration": "MH12AB1234", "password": "should_be_redacted"}
        )

        events = repo.query_audit_events(action="TARGET_CREATED")
        assert len(events) == 1
        ev = events[0]
        assert ev.actor_username == "admin_user"
        assert ev.actor_role == "ADMIN"
        assert ev.resource_type == "target"
        assert ev.resource_id == "tgt-99"
        assert ev.details_json["password"] == "[REDACTED]"
