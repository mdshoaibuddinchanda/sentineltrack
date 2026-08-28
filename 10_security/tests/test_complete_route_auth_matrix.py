import sys
import importlib
import pytest
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

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
        repo.save_user(u)
        users[role] = uname
    return users


def _get_client_for_user(username):
    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": username, "password": "Password123456789!"})
    csrf = login_res.json().get("csrf_token", "")
    return client, csrf


def test_programmatic_route_introspection_unauthenticated(clean_security_env):
    """
    Programmatically enumerates all registered FastAPI routes in _backend.app.routes.
    Verifies that every non-public endpoint rejects unauthenticated requests with 401.
    """
    client = TestClient(_backend.app)
    public_paths = {"/health", "/api/v1/auth/login", "/docs", "/redoc", "/openapi.json"}

    introspected_routes = []
    for route in _backend.app.routes:
        if isinstance(route, APIRoute):
            path = route.path
            for method in route.methods:
                if method not in ("HEAD", "OPTIONS"):
                    introspected_routes.append((method, path))

    assert len(introspected_routes) >= 15, "Expected at least 15 registered routes in backend API"

    for method, path in introspected_routes:
        # Check if route is public
        if path in public_paths or any(path.startswith(p) for p in ("/docs", "/redoc")):
            continue

        # Replace path parameters with dummy values for request
        test_path = path.replace("{camera_id}", "cam_01")
        test_path = test_path.replace("{target_id}", "tgt_01")
        test_path = test_path.replace("{alert_id}", "alt_01")
        test_path = test_path.replace("{registration}", "GJ01AB1234")
        test_path = test_path.replace("{user_id}", "usr_01")

        if method == "GET":
            res = client.get(test_path)
        elif method == "POST":
            res = client.post(test_path, json={})
        elif method == "PATCH":
            res = client.patch(test_path, json={})
        elif method == "DELETE":
            res = client.delete(test_path)
        else:
            continue

        assert res.status_code in (401, 403), f"Route {method} {path} should require authentication, got {res.status_code}"


def test_operator_matrix_rbac(clean_security_env):
    """OPERATOR has read access to cameras/sightings/alerts/routes/system, but lacks user admin, target mutations, and audit logs."""
    repo, sm = clean_security_env
    users = _setup_users(repo)
    client, csrf = _get_client_for_user(users[UserRole.OPERATOR])

    # Allowed reads
    assert client.get("/api/v1/cameras").status_code == 200
    assert client.get("/api/v1/sightings").status_code == 200
    assert client.get("/api/v1/alerts").status_code == 200
    assert client.get("/api/v1/routes/GJ01AB1234").status_code == 200
    assert client.get("/ready").status_code in (200, 503)

    # Denied target mutations (403)
    assert client.post("/api/v1/targets", json={"registration": "GJ01XY9999", "priority": "HIGH"}, headers={"X-CSRF-Token": csrf}).status_code == 403
    assert client.patch("/api/v1/targets/tgt_01", json={"priority": "HIGH"}, headers={"X-CSRF-Token": csrf}).status_code == 403
    assert client.delete("/api/v1/targets/tgt_01", headers={"X-CSRF-Token": csrf}).status_code == 403

    # Denied user management (403)
    assert client.get("/api/v1/users").status_code == 403
    assert client.post("/api/v1/users", json={"username": "test", "display_name": "Test", "password": "Password123456789!"}, headers={"X-CSRF-Token": csrf}).status_code == 403

    # Denied audit read (403)
    assert client.get("/api/v1/audit").status_code == 403


def test_auditor_matrix_rbac(clean_security_env):
    """AUDITOR has read access to audit logs/sightings/cameras/alerts, but cannot ACK alerts or mutate targets/users."""
    repo, sm = clean_security_env
    users = _setup_users(repo)
    client, csrf = _get_client_for_user(users[UserRole.AUDITOR])

    # Allowed audit read
    assert client.get("/api/v1/audit").status_code == 200
    assert client.get("/api/v1/sightings").status_code == 200
    assert client.get("/api/v1/cameras").status_code == 200

    # Denied alert ACK (403)
    assert client.post("/api/v1/alerts/alt-123/ack", json={}, headers={"X-CSRF-Token": csrf}).status_code == 403

    # Denied target create (403)
    assert client.post("/api/v1/targets", json={"registration": "GJ01XY9999", "priority": "HIGH"}, headers={"X-CSRF-Token": csrf}).status_code == 403


def test_supervisor_matrix_rbac(clean_security_env):
    """SUPERVISOR can manage targets and ACK alerts, but cannot access user admin endpoints."""
    repo, sm = clean_security_env
    users = _setup_users(repo)
    client, csrf = _get_client_for_user(users[UserRole.SUPERVISOR])

    # Allowed target mutations (authorized: status not 401/403)
    target_res = client.post("/api/v1/targets", json={"registration": "GJ01XY8888", "priority": "CRITICAL"}, headers={"X-CSRF-Token": csrf})
    assert target_res.status_code in (201, 409)

    # Denied user management (403)
    assert client.get("/api/v1/users").status_code == 403
    assert client.post("/api/v1/users", json={"username": "test", "display_name": "Test", "password": "Password123456789!"}, headers={"X-CSRF-Token": csrf}).status_code == 403


def test_admin_matrix_rbac(clean_security_env):
    """ADMIN has full authorization across all administrative and operational routes."""
    repo, sm = clean_security_env
    users = _setup_users(repo)
    client, csrf = _get_client_for_user(users[UserRole.ADMIN])

    assert client.get("/api/v1/cameras").status_code == 200
    assert client.get("/api/v1/users").status_code == 200
    assert client.get("/api/v1/audit").status_code == 200
    assert client.get("/ready").status_code in (200, 503)
    assert client.get("/metrics").status_code == 200
