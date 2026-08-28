import sys
import importlib
import pytest
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


_sec_repo = importlib.import_module("10_security.repository")
_sec_sess = importlib.import_module("10_security.sessions")
_sec_pw = importlib.import_module("10_security.password")
_sec_models = importlib.import_module("10_security.models")
_sec_perms = importlib.import_module("10_security.permissions")
_backend = importlib.import_module("08_backend.app")

SqliteSecurityRepository = _sec_repo.SqliteSecurityRepository
set_security_repository = _sec_repo.set_security_repository
SessionManager = _sec_sess.SessionManager
set_session_manager = _sec_sess.set_session_manager
hash_password = _sec_pw.hash_password
User = _sec_models.User
UserRole = _sec_models.UserRole
Permission = _sec_models.Permission
ROLE_PERMISSIONS = _sec_perms.ROLE_PERMISSIONS

PUBLIC = "PUBLIC"
AUTHENTICATED_ONLY = "AUTHENTICATED_ONLY"

# Canonical Policy Table mapping (HTTP_METHOD, ROUTE_PATH) -> Required Permission or Access Category
ROUTE_POLICY = {
    ("GET", "/health"): PUBLIC,
    ("POST", "/api/v1/auth/login"): PUBLIC,
    ("GET", "/api/v1/auth/csrf"): AUTHENTICATED_ONLY,
    ("GET", "/api/v1/auth/me"): AUTHENTICATED_ONLY,
    ("POST", "/api/v1/auth/logout"): AUTHENTICATED_ONLY,
    ("POST", "/api/v1/auth/change-password"): AUTHENTICATED_ONLY,


    ("GET", "/ready"): Permission.SYSTEM_READ,
    ("GET", "/metrics"): Permission.METRICS_READ,
    ("GET", "/metrics/prometheus"): Permission.METRICS_READ,


    ("GET", "/api/v1/cameras"): Permission.CAMERA_READ,
    ("GET", "/api/v1/cameras/nearby"): Permission.CAMERA_READ,
    ("GET", "/api/v1/cameras/{camera_id}"): Permission.CAMERA_READ,
    ("GET", "/api/v1/cameras/{camera_id}/health"): Permission.CAMERA_READ,
    ("GET", "/api/v1/cameras/{camera_id}/nearby"): Permission.CAMERA_READ,

    ("GET", "/api/v1/sightings"): Permission.SIGHTING_READ,
    ("GET", "/api/v1/vehicles/{registration}/history"): Permission.SIGHTING_READ,

    ("GET", "/api/v1/targets"): Permission.TARGET_READ,
    ("GET", "/api/v1/targets/{target_id}"): Permission.TARGET_READ,
    ("POST", "/api/v1/targets"): Permission.TARGET_CREATE,
    ("PATCH", "/api/v1/targets/{target_id}"): Permission.TARGET_UPDATE,
    ("DELETE", "/api/v1/targets/{target_id}"): Permission.TARGET_DISABLE,

    ("GET", "/api/v1/alerts"): Permission.ALERT_READ,
    ("GET", "/api/v1/alerts/{alert_id}"): Permission.ALERT_READ,
    ("POST", "/api/v1/alerts/{alert_id}/ack"): Permission.ALERT_ACK,

    ("GET", "/api/v1/routes/{registration}"): Permission.ROUTE_READ,
    ("GET", "/api/v1/routes/{registration}/geojson"): Permission.ROUTE_READ,
    ("GET", "/api/v1/routes/{registration}/summary"): Permission.ROUTE_READ,

    ("GET", "/api/v1/audit"): Permission.AUDIT_READ,

    ("GET", "/api/v1/users"): Permission.USER_READ,
    ("GET", "/api/v1/users/{user_id}"): Permission.USER_READ,
    ("POST", "/api/v1/users"): Permission.USER_CREATE,
    ("PATCH", "/api/v1/users/{user_id}"): Permission.USER_UPDATE,
    ("POST", "/api/v1/users/{user_id}/reset-password"): Permission.USER_RESET_PASSWORD,
}


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
        uname = f"usr_{role.value.lower()}"
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


def get_actual_application_routes() -> set[tuple[str, str]]:
    """
    Extracts all public HTTP path operations exposed by the FastAPI application.
    Uses OpenAPI schema as authoritative source, with route-tree fallback.
    """
    actual_routes: set[tuple[str, str]] = set()
    http_methods = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}

    # 1. Authoritative OpenAPI schema extraction
    openapi_schema = _backend.app.openapi()
    for path, path_item in openapi_schema.get("paths", {}).items():
        for method in path_item:
            if method.lower() in http_methods and method.lower() not in ("head", "options"):
                actual_routes.add((method.upper(), path))

    # 2. Structural route-tree traversal fallback/augmentation
    def _walk_routes(routes, prefix=""):
        for route in routes:
            child_routes = getattr(route, "routes", None)
            if child_routes:
                sub_prefix = prefix + getattr(route, "path", getattr(route, "prefix", ""))
                _walk_routes(child_routes, sub_prefix)
            elif isinstance(route, APIRoute):
                full_path = getattr(route, "path", "")
                for method in getattr(route, "methods", []):
                    if method not in ("HEAD", "OPTIONS") and not full_path.startswith(("/docs", "/redoc", "/openapi")):
                        actual_routes.add((method.upper(), full_path))

    _walk_routes(_backend.app.routes)
    return actual_routes


def test_d15_policy_coverage_invariant():
    """
    D15: Invariant test verifying that 100% of HTTP API routes exposed by the application
    are explicitly registered in ROUTE_POLICY with zero missing and zero stale routes.
    """
    actual_routes = get_actual_application_routes()

    # Sanity gates: verify route extraction was successful
    assert actual_routes, "Route inventory unexpectedly empty"
    assert ("POST", "/api/v1/auth/login") in actual_routes, "Sanity check failed: login route missing"
    assert ("GET", "/health") in actual_routes, "Sanity check failed: health route missing"
    assert ("GET", "/api/v1/cameras") in actual_routes, "Sanity check failed: cameras route missing"
    assert ("GET", "/metrics/prometheus") in actual_routes, "Sanity check failed: prometheus route missing"

    policy_routes = set(ROUTE_POLICY.keys())

    missing_from_policy = actual_routes - policy_routes
    assert not missing_from_policy, f"Routes missing from ROUTE_POLICY: {missing_from_policy}"

    stale_in_policy = policy_routes - actual_routes
    assert not stale_in_policy, f"Stale routes in ROUTE_POLICY that do not exist in application: {stale_in_policy}"



def test_d16_unauthenticated_route_rejection(clean_security_env):
    """D16: All protected routes reject unauthenticated requests with HTTP 401."""
    client = TestClient(_backend.app)

    for (method, path), policy in ROUTE_POLICY.items():
        if policy == PUBLIC:
            continue

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

        assert res.status_code in (401, 403), f"Route {method} {path} should reject unauthenticated request with 401, got {res.status_code}"


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.OPERATOR, UserRole.AUDITOR])
def test_d16_role_permission_matrix(clean_security_env, role):
    """
    D16: Comprehensive method x route x role evaluation.
    Verifies that for each role, access is allowed if and only if the principal possesses the required permission.
    """
    repo, sm = clean_security_env
    users = _setup_users(repo)
    client, csrf = _get_client_for_user(users[role])
    role_perms = ROLE_PERMISSIONS[role]

    for (method, path), required_perm in ROUTE_POLICY.items():
        test_path = path.replace("{camera_id}", "cam_01")
        test_path = test_path.replace("{target_id}", "tgt_01")
        test_path = test_path.replace("{alert_id}", "alt_01")
        test_path = test_path.replace("{registration}", "GJ01AB1234")
        test_path = test_path.replace("{user_id}", "id_usr_operator")

        req_client = client

        # Destructive auth endpoints use dedicated sub-client so they do not invalidate main session
        if path in ("/api/v1/auth/logout", "/api/v1/auth/change-password"):
            tmp_username = f"tmp_{role.value.lower()}_{hash(path) % 10000}"
            tmp_u = User(
                user_id=f"id_{tmp_username}",
                username=tmp_username,
                display_name=f"Tmp {role.value}",
                password_hash=hash_password("Password123456789!"),
                role=role,
                enabled=True
            )
            repo.save_user(tmp_u)
            req_client, _ = _get_client_for_user(tmp_username)

        csrf_res = req_client.get("/api/v1/auth/csrf")
        req_csrf = csrf_res.json().get("csrf_token", "")
        headers = {"X-CSRF-Token": req_csrf}

        # Determine expected access
        if required_perm == PUBLIC or required_perm == AUTHENTICATED_ONLY:
            allowed = True
        else:
            perm_val = required_perm.value if hasattr(required_perm, "value") else str(required_perm)
            allowed = perm_val in role_perms or required_perm in role_perms

        # Perform request with valid test body if mutation
        if method == "GET":
            res = req_client.get(test_path)
        elif method == "POST":
            payload = {}
            if "targets" in path:
                payload = {"registration": "GJ01AB9999", "priority": "NORMAL"}
            elif "users" in path and "reset-password" in path:
                payload = {"new_password": "NewPassword12345!"}
            elif "users" in path:
                payload = {"username": f"user_new_{role.value}_{hash(path) % 10000}", "display_name": "New", "password": "Password123456789!", "role": "OPERATOR"}
            elif "change-password" in path:
                payload = {"current_password": "Password123456789!", "new_password": "NewPassword12345!"}
            res = req_client.post(test_path, json=payload, headers=headers)
        elif method == "PATCH":
            res = req_client.patch(test_path, json={"display_name": "Updated"}, headers=headers)
        elif method == "DELETE":
            res = req_client.delete(test_path, headers=headers)
        else:
            continue

        if not allowed:
            assert res.status_code == 403, f"Role {role.value} should be DENIED 403 on {method} {path}, got {res.status_code}"
        else:
            assert res.status_code != 401 and res.status_code != 403, f"Role {role.value} should be AUTHORIZED on {method} {path}, got {res.status_code} ({res.text})"



