import os
import sys
import importlib
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


_sec_repo = importlib.import_module("10_security.repository")
_sec_sess = importlib.import_module("10_security.sessions")
_sec_pw = importlib.import_module("10_security.password")
_sec_models = importlib.import_module("10_security.models")
_sec_csrf = importlib.import_module("10_security.csrf")
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


def _create_user(repo, username="admin_p10b", role=UserRole.ADMIN, password="Password123456789!"):
    user = User(
        user_id=f"usr-{username}",
        username=username,
        display_name="Test Operator",
        password_hash=hash_password(password),
        role=role,
        enabled=True
    )
    repo.save_user(user)
    return user


def test_a3_csrf_rotation_persistence(clean_security_env):
    """A3: /auth/csrf rotates CSRF token on existing session and persists to repository."""
    repo, sm = clean_security_env
    user = _create_user(repo, "user_csrf_rot", UserRole.ADMIN)
    
    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "user_csrf_rot", "password": "Password123456789!"})
    assert login_res.status_code == 200
    token_a = login_res.json()["csrf_token"]

    csrf_res = client.get("/api/v1/auth/csrf")
    assert csrf_res.status_code == 200
    token_b = csrf_res.json()["csrf_token"]
    assert token_a != token_b

    logout_res = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": token_b})
    assert logout_res.status_code == 200


def test_a4_logout_requires_csrf(clean_security_env):
    """A4: POST /auth/logout must validate CSRF token."""
    repo, sm = clean_security_env
    user = _create_user(repo, "user_logout_csrf", UserRole.OPERATOR)
    
    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "user_logout_csrf", "password": "Password123456789!"})
    csrf_token = login_res.json()["csrf_token"]

    # 1. Missing CSRF header -> 403
    client2 = TestClient(_backend.app, cookies=client.cookies)
    assert client2.post("/api/v1/auth/logout").status_code == 403

    # 2. Invalid CSRF header -> 403
    assert client2.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "bad_token"}).status_code == 403

    # 3. Valid CSRF header -> 200
    assert client2.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_token}).status_code == 200


def test_a7_password_change_revokes_all_sessions(clean_security_env):
    """A7: Password change revokes all active sessions across devices."""
    repo, sm = clean_security_env
    user = _create_user(repo, "user_pw_rev", UserRole.OPERATOR, "OldPassword123456789!")
    
    client1 = TestClient(_backend.app)
    login1 = client1.post("/api/v1/auth/login", json={"username": "user_pw_rev", "password": "OldPassword123456789!"})
    csrf1 = login1.json()["csrf_token"]

    client2 = TestClient(_backend.app)
    login2 = client2.post("/api/v1/auth/login", json={"username": "user_pw_rev", "password": "OldPassword123456789!"})
    assert login2.status_code == 200

    chg_res = client1.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPassword123456789!", "new_password": "NewSecurePassword123456!"},
        headers={"X-CSRF-Token": csrf1}
    )
    assert chg_res.status_code == 200
    assert client2.get("/api/v1/auth/me").status_code == 401
    assert client1.get("/api/v1/auth/me").status_code == 401


def test_role_change_revokes_all_sessions(clean_security_env):
    """P10C: Updating a user's role immediately revokes all of their active sessions."""
    repo, sm = clean_security_env
    admin = _create_user(repo, "admin_role_mgr", UserRole.ADMIN)
    target_user = _create_user(repo, "op_to_promote", UserRole.OPERATOR)

    # Operator logs in
    op_client = TestClient(_backend.app)
    op_login = op_client.post("/api/v1/auth/login", json={"username": "op_to_promote", "password": "Password123456789!"})
    assert op_login.status_code == 200
    assert op_client.get("/api/v1/auth/me").status_code == 200

    # Admin changes operator role to SUPERVISOR
    admin_client = TestClient(_backend.app)
    admin_login = admin_client.post("/api/v1/auth/login", json={"username": "admin_role_mgr", "password": "Password123456789!"})
    admin_csrf = admin_login.json()["csrf_token"]

    patch_res = admin_client.patch(
        f"/api/v1/users/{target_user.user_id}",
        json={"role": "SUPERVISOR"},
        headers={"X-CSRF-Token": admin_csrf}
    )
    assert patch_res.status_code == 200

    # Operator's prior session is now revoked (must log in again under new role)
    assert op_client.get("/api/v1/auth/me").status_code == 401


def test_audit_failure_compensates_user_update(clean_security_env):
    """P10C: When fail-closed audit log write fails on user update, state is restored and 500 returned."""
    repo, sm = clean_security_env
    admin = _create_user(repo, "admin_audit_comp", UserRole.ADMIN)
    user = _create_user(repo, "user_to_update", UserRole.OPERATOR)

    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "admin_audit_comp", "password": "Password123456789!"})
    csrf = login_res.json()["csrf_token"]

    # Mock audit logger to raise exception
    audit_mod = importlib.import_module("10_security.audit")
    with patch.object(audit_mod.AuditLogger, "log_event", side_effect=RuntimeError("Audit disk full")):
        patch_res = client.patch(
            f"/api/v1/users/{user.user_id}",
            json={"display_name": "Tampered Display Name"},
            headers={"X-CSRF-Token": csrf}
        )
        assert patch_res.status_code == 500

    # Verify user display name was restored to original
    refetched = repo.get_user_by_id(user.user_id)
    assert refetched.display_name == "Test Operator"


def test_a8_security_repository_fail_closed_in_production(monkeypatch):
    """A8: Production mode fails closed with Postgres error; NO silent SQLite in-memory fallback."""
    monkeypatch.setenv("SENTINEL_ENV", "production")
    monkeypatch.setenv("SENTINEL_SECURITY_USE_SQLITE", "true")
    
    _repo_mod = importlib.import_module("10_security.repository")
    _repo_mod.set_security_repository(None)
    
    with pytest.raises(RuntimeError, match="strictly forbidden in production"):
        _repo_mod.get_security_repository()


def test_a9_production_disables_docs(monkeypatch):
    """A9: In production mode, FastAPI docs (/docs, /redoc, /openapi.json) are disabled."""
    monkeypatch.setenv("SENTINEL_ENV", "production")
    _sec_cfg = importlib.import_module("10_security.config")
    _sec_cfg.set_security_config(None)
    
    app_mod = importlib.import_module("08_backend.app")
    prod_app = app_mod.create_app()
    client = TestClient(prod_app)
    
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    _sec_cfg.set_security_config(None)


def test_a10_health_ready_and_metrics_auth(clean_security_env):
    """A10: /health is public; /ready requires system:read; /metrics requires metrics:read."""
    repo, sm = clean_security_env
    client = TestClient(_backend.app)

    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 401
    assert client.get("/metrics").status_code == 401

    user_op = _create_user(repo, "op_diag", UserRole.OPERATOR)
    client_op = TestClient(_backend.app)
    client_op.post("/api/v1/auth/login", json={"username": "op_diag", "password": "Password123456789!"})
    assert client_op.get("/metrics").status_code == 403
    assert client_op.get("/ready").status_code in (200, 503)

    user_sup = _create_user(repo, "sup_diag", UserRole.SUPERVISOR)
    client_sup = TestClient(_backend.app)
    client_sup.post("/api/v1/auth/login", json={"username": "sup_diag", "password": "Password123456789!"})
    assert client_sup.get("/metrics").status_code == 200


def test_a12_alert_acknowledgement_actor_from_session(clean_security_env):
    """A12: Alert acknowledgement ignores client-provided spoofed username and uses session identity."""
    repo, sm = clean_security_env
    user = _create_user(repo, "real_operator_alice", UserRole.OPERATOR)
    
    from datetime import datetime, timezone
    alt_m = importlib.import_module("08_backend.schemas.alerts")
    
    mock_service = MagicMock()
    mock_service.acknowledge_alert.side_effect = lambda alert_id, acknowledged_by: alt_m.AlertAckResponse(
        success=True,
        alert_id=alert_id,
        acknowledged=True,
        acknowledged_by=acknowledged_by,
        acknowledged_at=datetime.now(timezone.utc)
    )
    
    alerts_router_mod = importlib.import_module("08_backend.routers.alerts")
    _backend.app.dependency_overrides[alerts_router_mod.get_alert_service] = lambda: mock_service

    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "real_operator_alice", "password": "Password123456789!"})
    csrf_token = login_res.json()["csrf_token"]

    ack_res = client.post(
        "/api/v1/alerts/alt-test-123/ack",
        json={"acknowledged_by": "spoofed_chief_of_police"},
        headers={"X-CSRF-Token": csrf_token}
    )
    assert ack_res.status_code == 200
    data = ack_res.json()
    assert data["acknowledged_by"] == "real_operator_alice"
    assert data["acknowledged_by"] != "spoofed_chief_of_police"


def test_a13_last_admin_protection(clean_security_env):
    """A13: Demoting or disabling the only active admin returns 400 Bad Request."""
    repo, sm = clean_security_env
    admin_user = _create_user(repo, "sole_admin", UserRole.ADMIN)
    
    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "sole_admin", "password": "Password123456789!"})
    csrf_token = login_res.json()["csrf_token"]

    # Attempt to demote sole admin
    demote_res = client.patch(
        f"/api/v1/users/{admin_user.user_id}",
        json={"role": "OPERATOR"},
        headers={"X-CSRF-Token": csrf_token}
    )
    assert demote_res.status_code == 400
    assert "last remaining active administrator" in demote_res.json()["detail"]

    # Attempt to disable sole admin
    disable_res = client.patch(
        f"/api/v1/users/{admin_user.user_id}",
        json={"enabled": False},
        headers={"X-CSRF-Token": csrf_token}
    )
    assert disable_res.status_code == 400
    assert "last remaining active administrator" in disable_res.json()["detail"]
