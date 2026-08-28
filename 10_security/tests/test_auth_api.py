import pytest
import importlib
from pathlib import Path
import sys
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
def setup_security():
    test_repo = SqliteSecurityRepository(":memory:")
    test_session_manager = SessionManager(repository=test_repo)
    test_audit = _aud_mod.AuditLogger(repository=test_repo)

    # Seed Admin User
    admin = User(
        user_id="admin-1",
        username="admin",
        display_name="System Administrator",
        password_hash=hash_password("SuperSecretAdminPass123!"),
        role=UserRole.ADMIN,
        enabled=True
    )
    test_repo.save_user(admin)

    # Seed Operator User
    operator = User(
        user_id="op-1",
        username="operator",
        display_name="Field Operator",
        password_hash=hash_password("OperatorSecretPass123!"),
        role=UserRole.OPERATOR,
        enabled=True
    )
    test_repo.save_user(operator)

    _repo_mod.set_security_repository(test_repo)
    _sess_mod.set_session_manager(test_session_manager)
    _aud_mod.set_audit_logger(test_audit)

    yield test_repo, test_session_manager

    _repo_mod.set_security_repository(None)
    _sess_mod.set_session_manager(None)
    _aud_mod.set_audit_logger(None)



class TestAuthAPI:
    def test_login_success(self):
        client = TestClient(app)
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "SuperSecretAdminPass123!"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["username"] == "admin"
        assert data["role"] == "ADMIN"
        assert "csrf_token" in data
        assert "sentinel_session" in resp.cookies

    def test_login_wrong_password_returns_401(self):
        client = TestClient(app)
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "WrongPassword12345!"}
        )
        assert resp.status_code == 401

    def test_me_unauthenticated_returns_401(self):
        client = TestClient(app)
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_authenticated_returns_user_and_permissions(self):
        client = TestClient(app)
        # Login first
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "operator", "password": "OperatorSecretPass123!"}
        )
        assert login_resp.status_code == 200

        # Now call /me with cookie preserved
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["username"] == "operator"
        assert data["role"] == "OPERATOR"
        assert "camera:read" in data["permissions"]
        assert "user:create" not in data["permissions"]


    def test_logout_invalidates_session(self):
        client = TestClient(app)
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "SuperSecretAdminPass123!"}
        )
        csrf_token = login_resp.json()["csrf_token"]

        # Logout with CSRF token
        logout_resp = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token}
        )
        assert logout_resp.status_code == 200

        # Now /me should fail with 401
        me_resp = client.get("/api/v1/auth/me")
        assert me_resp.status_code == 401

    def test_csrf_token_endpoint(self):
        client = TestClient(app)
        client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "SuperSecretAdminPass123!"}
        )
        resp = client.get("/api/v1/auth/csrf")
        assert resp.status_code == 200
        assert "csrf_token" in resp.json()

    def test_login_timing_equalization_unknown_user(self):
        """Nonexistent username executes password verification on dummy hash and returns 401."""
        client = TestClient(app)
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent_operator_xyz", "password": "SomeRandomPassword123!"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password."

    def test_login_timing_equalization_disabled_user(self):
        """Disabled user executes dummy password verification and returns generic 401 without enumeration."""
        repo = _repo_mod.get_security_repository()
        disabled_user = User(
            user_id="disabled-1",
            username="disabled_operator",
            display_name="Disabled Operator",
            password_hash=hash_password("DisabledPass12345!"),
            role=UserRole.OPERATOR,
            enabled=False
        )
        repo.save_user(disabled_user)

        client = TestClient(app)
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "disabled_operator", "password": "DisabledPass12345!"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password."

