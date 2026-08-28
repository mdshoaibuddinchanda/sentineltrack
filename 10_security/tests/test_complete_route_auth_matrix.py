import sys
import importlib
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, "c:/DR2/sentineltrack")

_sec_repo = importlib.import_module("10_security.repository")
_sec_sess = importlib.import_module("10_security.sessions")
_sec_pw = importlib.import_module("10_security.password")
_sec_models = importlib.import_module("10_security.models")
_backend = importlib.import_module("08_backend.app")

SqliteSecurityRepository = _sec_repo.SqliteSecurityRepository
set_security_repository = _sec_repo.set_security_repository
SessionManager = _sec_sess.SessionManager
set_session_manager = _sec_sess.set_session_manager
hash_password = _sec_pw.hash_password
User = _sec_models.User
UserRole = _sec_models.UserRole


@pytest.fixture(autouse=True)
def clean_security_env():
    repo = SqliteSecurityRepository()
    set_security_repository(repo)
    sm = SessionManager(repo)
    set_session_manager(sm)
    saved_overrides = dict(_backend.app.dependency_overrides)
    _backend.app.dependency_overrides.clear()
    yield repo, sm
    _backend.app.dependency_overrides = saved_overrides
    set_security_repository(None)
    set_session_manager(None)


def _setup_users(repo):
    users = {}
    for role in [UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.OPERATOR, UserRole.AUDITOR]:
        uname = f"user_{role.value.lower()}"
        u = User(
            user_id=f"id_{uname}",
            username=uname,
            display_name=f"{role.value} User",
            password_hash=hash_password("Password123456789!"),
            role=role,
            enabled=True
        )
        repo.create_user(u)
        users[role] = uname
    return users


def _get_client_for_user(username):
    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": username, "password": "Password123456789!"})
    csrf = login_res.json().get("csrf_token", "")
    return client, csrf


def test_programmatic_route_matrix_unauthenticated(clean_security_env):
    """Verify unauthenticated requests to protected endpoints return 401."""
    client = TestClient(_backend.app)
    protected_get_paths = [
        "/ready",
        "/metrics",
        "/api/v1/cameras",
        "/api/v1/targets",
        "/api/v1/sightings",
        "/api/v1/alerts",
        "/api/v1/routes/GJ01AB1234",
        "/api/v1/users",
        "/api/v1/audit",
        "/api/v1/auth/me",
    ]
    for path in protected_get_paths:
        res = client.get(path)
        assert res.status_code == 401, f"Expected 401 for unauthenticated GET {path}, got {res.status_code}"


def test_operator_authorization_boundaries(clean_security_env):
    """Operator role can read cameras/alerts/sightings and ACK alerts, but cannot create targets or manage users."""
    repo, sm = clean_security_env
    users = _setup_users(repo)
    client, csrf = _get_client_for_user(users[UserRole.OPERATOR])

    # Allowed reads
    assert client.get("/api/v1/cameras").status_code == 200
    assert client.get("/api/v1/alerts").status_code == 200
    assert client.get("/api/v1/sightings").status_code == 200
    assert client.get("/api/v1/routes/GJ01AB1234").status_code == 200

    # Allowed alert ACK (status is 200 if alert exists or 404 if not found in db; never 401/403)
    assert client.post("/api/v1/alerts/alt-123/ack", json={}, headers={"X-CSRF-Token": csrf}).status_code in (200, 404)


    # Denied target creation (403)
    target_res = client.post("/api/v1/targets", json={"registration": "GJ01XY9999", "priority": "HIGH"}, headers={"X-CSRF-Token": csrf})
    assert target_res.status_code == 403

    # Denied user management (403)
    user_res = client.get("/api/v1/users")
    assert user_res.status_code == 403

    # Denied audit log read (403)
    audit_res = client.get("/api/v1/audit")
    assert audit_res.status_code == 403


def test_auditor_authorization_boundaries(clean_security_env):
    """Auditor role can read audit logs and sightings, but cannot ACK alerts or mutate targets."""
    repo, sm = clean_security_env
    users = _setup_users(repo)
    client, csrf = _get_client_for_user(users[UserRole.AUDITOR])

    # Allowed audit read
    assert client.get("/api/v1/audit").status_code == 200
    assert client.get("/api/v1/sightings").status_code == 200

    # Denied alert ACK (403)
    ack_res = client.post("/api/v1/alerts/alt-123/ack", json={}, headers={"X-CSRF-Token": csrf})
    assert ack_res.status_code == 403

    # Denied target create (403)
    target_res = client.post("/api/v1/targets", json={"registration": "GJ01XY9999", "priority": "HIGH"}, headers={"X-CSRF-Token": csrf})
    assert target_res.status_code == 403


def test_supervisor_authorization_boundaries(clean_security_env):
    """Supervisor can create/manage targets and ACK alerts, but cannot manage users."""
    repo, sm = clean_security_env
    users = _setup_users(repo)
    client, csrf = _get_client_for_user(users[UserRole.SUPERVISOR])

    # Allowed target create (201 Created or 409 Conflict if plate already registered; never 401/403)
    target_res = client.post("/api/v1/targets", json={"registration": "GJ01XY8888", "priority": "CRITICAL"}, headers={"X-CSRF-Token": csrf})
    assert target_res.status_code in (201, 409)


    # Allowed alert ACK (status is 200 if found or 404 if not in db; never 401/403)
    assert client.post("/api/v1/alerts/alt-123/ack", json={}, headers={"X-CSRF-Token": csrf}).status_code in (200, 404)


    # Denied user admin (403)
    assert client.get("/api/v1/users").status_code == 403


def test_admin_full_access(clean_security_env):
    """Admin has full authorization across all endpoints."""
    repo, sm = clean_security_env
    users = _setup_users(repo)
    client, csrf = _get_client_for_user(users[UserRole.ADMIN])

    assert client.get("/api/v1/cameras").status_code == 200
    assert client.get("/api/v1/users").status_code == 200
    assert client.get("/api/v1/audit").status_code == 200
    assert client.get("/ready").status_code in (200, 503)  # ready returns 200/503 based on subsystem status
