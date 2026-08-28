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

SQL_ATTACK_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE cameras; --",
    "1' UNION SELECT username, password_hash FROM security_users --",
    "admin'--",
    "\" OR \"\"=\"",
]

SHELL_METACHRS = [
    "; cat /etc/passwd",
    "| dir C:\\",
    "`whoami`",
    "$(reboot)",
    "&& echo hacked",
]

PATH_TRAVERSAL_PAYLOADS = [
    "../../../../windows/system32/cmd.exe",
    "..\\..\\..\\secret.env",
    "/etc/shadow",
    "C:\\secret.txt",
]


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


def _create_user(repo, username="sec_admin", role=UserRole.ADMIN, password="Password123456789!"):
    user = User(
        user_id=f"usr-{username}",
        username=username,
        display_name="Security Admin",
        password_hash=hash_password(password),
        role=role,
        enabled=True
    )
    repo.create_user(user)
    return user


def test_sql_injection_on_username_login(clean_security_env):
    """SQL injection payloads in username field do not bypass authentication or cause 500."""
    repo, sm = clean_security_env
    _create_user(repo, "real_admin", UserRole.ADMIN)
    client = TestClient(_backend.app)

    for payload in SQL_ATTACK_PAYLOADS:
        res = client.post("/api/v1/auth/login", json={"username": payload, "password": "wrong_password"})
        assert res.status_code in (401, 422)
        assert "500" not in str(res.status_code)


def test_sql_injection_on_target_creation_and_query(clean_security_env):
    """SQL injection strings in target registration, case_id, notes are treated strictly as literal data."""
    repo, sm = clean_security_env
    _create_user(repo, "sec_supervisor", UserRole.SUPERVISOR)
    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "sec_supervisor", "password": "Password123456789!"})
    csrf = login_res.json()["csrf_token"]

    for payload in SQL_ATTACK_PAYLOADS:
        res = client.post(
            "/api/v1/targets",
            json={"registration": f"GJ01{payload[:4]}", "priority": "HIGH", "notes": payload},
            headers={"X-CSRF-Token": csrf}
        )
        # Invalid registration format -> 400/422; duplicate -> 409; created -> 201; offline -> 503; never 500 SQL crash
        assert res.status_code in (201, 400, 409, 422, 503)
        assert res.status_code != 500




def test_command_injection_safety(clean_security_env):
    """Shell metacharacters in API inputs remain inert arguments and cannot execute commands."""
    repo, sm = clean_security_env
    _create_user(repo, "cmd_admin", UserRole.ADMIN)
    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "cmd_admin", "password": "Password123456789!"})
    csrf = login_res.json()["csrf_token"]

    for payload in SHELL_METACHRS:
        res = client.get(f"/api/v1/cameras/{payload}")
        assert res.status_code in (404, 422, 400)
        assert res.status_code != 500


def test_path_traversal_safety(clean_security_env):
    """Path traversal sequences in URL parameters are rejected without filesystem leakage."""
    repo, sm = clean_security_env
    _create_user(repo, "trav_admin", UserRole.ADMIN)
    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "trav_admin", "password": "Password123456789!"})

    for payload in PATH_TRAVERSAL_PAYLOADS:
        res = client.get(f"/api/v1/sightings/{payload}")
        assert res.status_code in (404, 422, 400)
        assert res.status_code != 500


def test_mass_assignment_forbidden_fields(clean_security_env):
    """Clients cannot smuggle forbidden fields like password_hash, permissions, or is_admin into request body."""
    repo, sm = clean_security_env
    user = _create_user(repo, "mass_admin", UserRole.ADMIN)
    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "mass_admin", "password": "Password123456789!"})
    csrf = login_res.json()["csrf_token"]

    # Attempt to smuggle password_hash or permissions directly in user update
    res = client.patch(
        f"/api/v1/users/{user.user_id}",
        json={"display_name": "New Name", "password_hash": "stolen_hash", "permissions": ["ALL"]},
        headers={"X-CSRF-Token": csrf}
    )
    assert res.status_code == 200
    # Verify password_hash was NOT modified
    updated_user = repo.get_user_by_id(user.user_id)
    assert updated_user.password_hash == user.password_hash
