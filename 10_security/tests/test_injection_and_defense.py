import os
import re
import sys
from pathlib import Path
import importlib
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_sec_repo = importlib.import_module("10_security.repository")
_sec_sess = importlib.import_module("10_security.sessions")
_sec_pw = importlib.import_module("10_security.password")
_sec_models = importlib.import_module("10_security.models")
_sec_audit = importlib.import_module("10_security.audit")
_backend = importlib.import_module("08_backend.app")

SqliteSecurityRepository = _sec_repo.SqliteSecurityRepository
set_security_repository = _sec_repo.set_security_repository
SessionManager = _sec_sess.SessionManager
set_session_manager = _sec_sess.set_session_manager
hash_password = _sec_pw.hash_password
User = _sec_models.User
UserRole = _sec_models.UserRole
AuthenticatedPrincipal = _sec_models.AuthenticatedPrincipal

SQL_ATTACK_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE cameras; --",
    "1' UNION SELECT username, password_hash FROM security_users --",
    "admin'--",
    "\" OR \"\"=\"",
]

DANGEROUS_PATTERNS = {
    "shell_true": re.compile(r"shell\s*=\s*True"),
    "os_system": re.compile(r"os\.system\s*\("),
    "subprocess_popen": re.compile(r"subprocess\.Popen\s*\("),
    "eval": re.compile(r"(?<![a-zA-Z0-9_])eval\s*\("),
    "exec": re.compile(r"(?<![a-zA-Z0-9_])exec\s*\("),
    "pickle_loads": re.compile(r"pickle\.loads\s*\("),
    "yaml_unsafe_load": re.compile(r"yaml\.load\s*\([^,)]*\)"),
    "dangerously_set_inner_html": re.compile(r"dangerouslySetInnerHTML"),
    "inner_html_assignment": re.compile(r"\.innerHTML\s*="),
    "document_write": re.compile(r"document\.write\s*\("),
    "new_function": re.compile(r"new\s+Function\s*\("),
}

# Explicit reviewed allowlist for verified safe occurrences (e.g. tests or build scripts)
REVIEWED_ALLOWLIST = {
    # e.g. ("filename.py", "pattern_name", "reason")
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


def _create_user(repo, username="sec_admin", role=UserRole.ADMIN, password="Password123456789!"):
    user = User(
        user_id=f"usr-{username}",
        username=username,
        display_name="Security Admin",
        password_hash=hash_password(password),
        role=role,
        enabled=True
    )
    repo.save_user(user)
    return user


def test_d19_source_level_dangerous_sink_scanner():
    """
    D19: Real source-level AST/regex scanner over tracked Python and TypeScript source code.
    Asserts zero unreviewed dangerous evaluation sinks exist across production modules.
    """
    root_dir = str(REPO_ROOT)
    scanned_dirs = [
        "00_ingestion", "01_pipeline", "02_tracking", "03_license_plate",
        "04_search_ocr", "05_target_matching", "07_trajectory", "08_backend",
        "09_dashboard/src", "10_security"
    ]

    violations = []
    scanned_file_count = 0

    for sdir in scanned_dirs:
        full_sdir = os.path.join(root_dir, sdir)

        if not os.path.exists(full_sdir):
            continue
        for root, dirs, files in os.walk(full_sdir):
            # Skip test directories, node_modules, and cache
            if any(skip in root for skip in ["node_modules", "dist", ".git", "__pycache__", "tests"]):
                continue
            for file in files:
                if not file.endswith((".py", ".ts", ".tsx")):
                    continue
                scanned_file_count += 1
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    for line_num, line in enumerate(lines, start=1):
                        for pattern_name, regex in DANGEROUS_PATTERNS.items():
                            if regex.search(line):
                                rel_path = os.path.relpath(filepath, root_dir)
                                if (rel_path, pattern_name) not in REVIEWED_ALLOWLIST:
                                    violations.append((rel_path, line_num, pattern_name, line.strip()))
                except Exception as exc:
                    violations.append((filepath, 0, "read_error", str(exc)))

    assert scanned_file_count >= 20, f"Expected to scan at least 20 source files, scanned {scanned_file_count}"
    assert len(violations) == 0, f"Found unreviewed dangerous sink patterns in source code: {violations}"


def test_d21_mass_assignment_forbid_on_all_mutation_schemas(clean_security_env):
    """
    D21: Enforces that unexpected JSON fields in mutation requests are rejected with HTTP 422
    across User, Target, Alert, and Auth schemas.
    """
    repo, sm = clean_security_env
    user = _create_user(repo, "mass_assign_admin", UserRole.ADMIN)
    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "mass_assign_admin", "password": "Password123456789!"})
    csrf = login_res.json()["csrf_token"]

    # 1. LoginRequest with extra field -> 422
    res_login = client.post("/api/v1/auth/login", json={"username": "mass_assign_admin", "password": "Password123456789!", "is_admin": True})
    assert res_login.status_code == 422

    # 2. ChangePasswordRequest with extra field -> 422
    res_cp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "Password123456789!", "new_password": "NewSecurePassword12345!", "force": True},
        headers={"X-CSRF-Token": csrf}
    )
    assert res_cp.status_code == 422

    # 3. UserCreateRequest with extra field -> 422
    res_uc = client.post(
        "/api/v1/users",
        json={"username": "new_op", "display_name": "New", "password": "Password123456789!", "role": "OPERATOR", "permissions": ["*"]},
        headers={"X-CSRF-Token": csrf}
    )
    assert res_uc.status_code == 422

    # 4. UserUpdateRequest with extra field -> 422
    res_uu = client.patch(
        f"/api/v1/users/{user.user_id}",
        json={"display_name": "New Name", "password_hash": "tampered_hash"},
        headers={"X-CSRF-Token": csrf}
    )
    assert res_uu.status_code == 422

    # 5. UserResetPasswordRequest with extra field -> 422
    res_urp = client.post(
        f"/api/v1/users/{user.user_id}/reset-password",
        json={"new_password": "NewResetPassword12345!", "role": "SUPERVISOR"},
        headers={"X-CSRF-Token": csrf}
    )
    assert res_urp.status_code == 422

    # 6. TargetCreateRequest with extra field -> 422
    res_tc = client.post(
        "/api/v1/targets",
        json={"registration": "GJ01MASS123", "priority": "NORMAL", "is_admin": True},
        headers={"X-CSRF-Token": csrf}
    )
    assert res_tc.status_code == 422

    # 7. TargetUpdateRequest with extra field -> 422
    res_tu = client.patch(
        "/api/v1/targets/tgt_01",
        json={"priority": "CRITICAL", "raw_sql": "SELECT 1"},
        headers={"X-CSRF-Token": csrf}
    )
    assert res_tu.status_code == 422

    # 8. AlertAckRequest with extra field -> 422
    res_aa = client.post(
        "/api/v1/alerts/alt_01/ack",
        json={"acknowledged_by": "operator", "tampered_score": 0.0},
        headers={"X-CSRF-Token": csrf}
    )
    assert res_aa.status_code == 422


def test_d20_sql_parameterization_on_repositories(clean_security_env):
    """
    D20: Verifies that SQL injection strings are safely parameterized and treated as literal values.
    No SQL syntax error occurs; queries return None or 401 cleanly.
    """
    repo, sm = clean_security_env
    _create_user(repo, "real_admin", UserRole.ADMIN)
    client = TestClient(_backend.app)

    for payload in SQL_ATTACK_PAYLOADS:
        # Repository query treats string as literal
        user = repo.get_user_by_username(payload)
        assert user is None  # Not found, never raises SQL syntax error

        # Login with SQL payload returns 401 or 422, never 500
        res = client.post("/api/v1/auth/login", json={"username": payload, "password": "wrong_password"})
        assert res.status_code in (401, 422)


def test_d22_log_injection_prevention(clean_security_env):
    """
    D22: Verifies that newline characters and control bytes injected into usernames, actions,
    or details are stripped and sanitized, preventing log forging and audit injection.
    """
    repo, sm = clean_security_env
    logger = _sec_audit.AuditLogger(repo)

    # 1. Test explicit malicious actor_username with newline/fake log injection
    malicious_user = "operator\n[AUDIT] action=USER_ADMIN resource=ALL actor=admin outcome=SUCCESS"
    event1 = logger.log_event(
        action="LOGIN_FAILURE\r\n[CRITICAL] FORGED",
        resource_type="auth\nadmin",
        actor_username=malicious_user,
        details={"note": "Multiline\nattempt\r\ninjection"}
    )

    assert "\n" not in event1.actor_username
    assert "\r" not in event1.actor_username
    assert "\n" not in event1.action
    assert "\r" not in event1.action
    assert "\n" not in event1.resource_type
    assert "\n" not in event1.details_json.get("note", "")

    # 2. Test principal with potential newline in username
    malicious_principal = AuthenticatedPrincipal(
        user_id="usr_fake",
        username="supervisor\n[FAKE_LOG_ENTRY]",
        display_name="Supervisor",
        role=UserRole.SUPERVISOR,
        permissions=set(),
        session_id="sess_fake"
    )

    event2 = logger.log_event(
        action="TARGET_CREATE",
        resource_type="target",
        principal=malicious_principal
    )

    assert "\n" not in event2.actor_username
    assert "\r" not in event2.actor_username
    assert event2.actor_username == "supervisor [FAKE_LOG_ENTRY]"

