import pytest
import importlib
from fastapi.testclient import TestClient

_sec = importlib.import_module("10_security")
User = _sec.User
UserRole = _sec.UserRole
hash_password = _sec.hash_password
_repo_mod = importlib.import_module("10_security.repository")
SqliteSecurityRepository = _repo_mod.SqliteSecurityRepository
_sess_mod = importlib.import_module("10_security.sessions")
SessionManager = _sess_mod.SessionManager

backend_app = importlib.import_module("08_backend.app")
app = backend_app.app


_aud_mod = importlib.import_module("10_security.audit")


@pytest.fixture(autouse=True)
def setup_users():
    test_repo = SqliteSecurityRepository(":memory:")
    test_session_manager = SessionManager(repository=test_repo)
    test_audit = _aud_mod.AuditLogger(repository=test_repo)

    # Seed Admin
    test_repo.save_user(User(
        user_id="admin-id",
        username="admin_user",
        display_name="Admin",
        password_hash=hash_password("SuperSecretAdminPass123!"),
        role=UserRole.ADMIN,
        enabled=True
    ))

    # Seed Supervisor
    test_repo.save_user(User(
        user_id="sup-id",
        username="supervisor_user",
        display_name="Supervisor",
        password_hash=hash_password("SuperSecretSupPass123!"),
        role=UserRole.SUPERVISOR,
        enabled=True
    ))

    # Seed Operator
    test_repo.save_user(User(
        user_id="op-id",
        username="operator_user",
        display_name="Operator",
        password_hash=hash_password("SuperSecretOpPass123!"),
        role=UserRole.OPERATOR,
        enabled=True
    ))

    # Seed Auditor
    test_repo.save_user(User(
        user_id="aud-id",
        username="auditor_user",
        display_name="Auditor",
        password_hash=hash_password("SuperSecretAudPass123!"),
        role=UserRole.AUDITOR,
        enabled=True
    ))

    _repo_mod.set_security_repository(test_repo)
    _sess_mod.set_session_manager(test_session_manager)
    _aud_mod.set_audit_logger(test_audit)

    yield test_repo

    _repo_mod.set_security_repository(None)
    _sess_mod.set_session_manager(None)
    _aud_mod.set_audit_logger(None)



class TestAuthorizationMatrix:
    def test_unauthenticated_request_rejected_with_401(self):
        client = TestClient(app)
        resp = client.get("/api/v1/cameras")
        assert resp.status_code == 401

    def test_operator_can_read_cameras_and_sightings(self):
        client = TestClient(app)
        client.post(
            "/api/v1/auth/login",
            json={"username": "operator_user", "password": "SuperSecretOpPass123!"}
        )
        cam_resp = client.get("/api/v1/cameras")
        assert cam_resp.status_code == 200

        sight_resp = client.get("/api/v1/sightings")
        assert sight_resp.status_code == 200

    def test_operator_cannot_access_user_admin_returns_403(self):
        client = TestClient(app)
        client.post(
            "/api/v1/auth/login",
            json={"username": "operator_user", "password": "SuperSecretOpPass123!"}
        )
        resp = client.get("/api/v1/users")
        assert resp.status_code == 403

    def test_operator_cannot_create_target_returns_403(self):
        client = TestClient(app)
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "operator_user", "password": "SuperSecretOpPass123!"}
        )
        csrf = login_resp.json()["csrf_token"]

        resp = client.post(
            "/api/v1/targets",
            json={"registration": "MH12AB9999", "priority": "HIGH"},
            headers={"X-CSRF-Token": csrf}
        )
        assert resp.status_code == 403

    def test_admin_can_access_user_admin(self):
        client = TestClient(app)
        client.post(
            "/api/v1/auth/login",
            json={"username": "admin_user", "password": "SuperSecretAdminPass123!"}
        )
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200

    def test_auditor_can_access_audit_log_but_operator_cannot(self):
        # Auditor access
        auditor_client = TestClient(app)
        auditor_client.post(
            "/api/v1/auth/login",
            json={"username": "auditor_user", "password": "SuperSecretAudPass123!"}
        )
        aud_resp = auditor_client.get("/api/v1/audit")
        assert aud_resp.status_code == 200

        # Operator access -> 403
        op_client = TestClient(app)
        op_client.post(
            "/api/v1/auth/login",
            json={"username": "operator_user", "password": "SuperSecretOpPass123!"}
        )
        op_resp = op_client.get("/api/v1/audit")
        assert op_resp.status_code == 403

    def test_post_without_csrf_token_returns_403(self):
        client = TestClient(app)
        client.post(
            "/api/v1/auth/login",
            json={"username": "admin_user", "password": "SuperSecretAdminPass123!"}
        )
        # Attempt POST without X-CSRF-Token header
        resp = client.post(
            "/api/v1/users",
            json={
                "username": "newuser",
                "display_name": "New User",
                "password": "Password123456789!",
                "role": "OPERATOR"
            }
        )
        assert resp.status_code == 403
