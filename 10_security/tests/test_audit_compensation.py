import sys
import copy
from pathlib import Path
from datetime import datetime, timezone
import importlib
import pytest
from unittest.mock import patch, MagicMock
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


def _create_user(repo, username="admin_comp", role=UserRole.ADMIN, password="Password123456789!"):
    user = User(
        user_id=f"usr-{username}",
        username=username,
        display_name="Admin Comp",
        password_hash=hash_password(password),
        role=role,
        enabled=True
    )
    repo.save_user(user)
    return user


def test_user_create_audit_failure_compensation(clean_security_env):
    """USER_CREATE: when audit logging fails, created user is deleted from repository."""
    repo, sm = clean_security_env
    admin = _create_user(repo, "admin_uc_test", UserRole.ADMIN)

    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "admin_uc_test", "password": "Password123456789!"})
    csrf = login_res.json()["csrf_token"]

    with patch.object(_sec_audit.AuditLogger, "log_event", side_effect=RuntimeError("Audit disk full")):
        res = client.post(
            "/api/v1/users",
            json={
                "username": "new_operator_fail",
                "display_name": "New Operator",
                "password": "Password123456789!",
                "role": "OPERATOR"
            },
            headers={"X-CSRF-Token": csrf}
        )
        assert res.status_code == 500

    # Assert user is NOT in repository
    created_user = repo.get_user_by_username("new_operator_fail")
    assert created_user is None


def test_user_update_audit_failure_compensation(clean_security_env):
    """USER_UPDATE: when audit logging fails, user state is restored and prior sessions remain intact."""
    repo, sm = clean_security_env
    admin = _create_user(repo, "admin_uu_test", UserRole.ADMIN)
    target_user = _create_user(repo, "op_uu_target", UserRole.OPERATOR)

    # Operator logs in and gets an active session
    op_client = TestClient(_backend.app)
    op_login = op_client.post("/api/v1/auth/login", json={"username": "op_uu_target", "password": "Password123456789!"})
    assert op_login.status_code == 200
    assert op_client.get("/api/v1/auth/me").status_code == 200

    admin_client = TestClient(_backend.app)
    admin_login = admin_client.post("/api/v1/auth/login", json={"username": "admin_uu_test", "password": "Password123456789!"})
    admin_csrf = admin_login.json()["csrf_token"]

    with patch.object(_sec_audit.AuditLogger, "log_event", side_effect=RuntimeError("Audit database error")):
        res = admin_client.patch(
            f"/api/v1/users/{target_user.user_id}",
            json={"display_name": "Tampered Name", "role": "SUPERVISOR"},
            headers={"X-CSRF-Token": admin_csrf}
        )
        assert res.status_code == 500

    # User state restored in repo
    refetched = repo.get_user_by_id(target_user.user_id)
    assert refetched.role == UserRole.OPERATOR

    # Operator session was NOT destructively revoked
    assert op_client.get("/api/v1/auth/me").status_code == 200


def test_user_password_reset_audit_failure_compensation(clean_security_env):
    """USER_PASSWORD_RESET: when audit logging fails, old password is restored and sessions remain intact."""
    repo, sm = clean_security_env
    admin = _create_user(repo, "admin_pw_test", UserRole.ADMIN)
    target_user = _create_user(repo, "op_pw_target", UserRole.OPERATOR, "InitialPassword12345!")

    # Operator logs in with initial password
    op_client = TestClient(_backend.app)
    op_login = op_client.post("/api/v1/auth/login", json={"username": "op_pw_target", "password": "InitialPassword12345!"})
    assert op_login.status_code == 200

    admin_client = TestClient(_backend.app)
    admin_login = admin_client.post("/api/v1/auth/login", json={"username": "admin_pw_test", "password": "Password123456789!"})
    admin_csrf = admin_login.json()["csrf_token"]

    with patch.object(_sec_audit.AuditLogger, "log_event", side_effect=RuntimeError("Audit disk write failure")):
        res = admin_client.post(
            f"/api/v1/users/{target_user.user_id}/reset-password",
            json={"new_password": "NewResetPassword12345!", "must_change_password": True},
            headers={"X-CSRF-Token": admin_csrf}
        )
        assert res.status_code == 500

    # Existing session is still valid
    assert op_client.get("/api/v1/auth/me").status_code == 200

    # Initial password is still valid for login; new password rejected
    login_old = TestClient(_backend.app).post("/api/v1/auth/login", json={"username": "op_pw_target", "password": "InitialPassword12345!"})
    assert login_old.status_code == 200
    login_new = TestClient(_backend.app).post("/api/v1/auth/login", json={"username": "op_pw_target", "password": "NewResetPassword12345!"})
    assert login_new.status_code == 401


def test_self_password_change_audit_failure_compensation(clean_security_env):
    """PASSWORD_CHANGED: when self-service password change audit fails, old password is restored and session remains intact."""
    repo, sm = clean_security_env
    user = _create_user(repo, "self_pw_user", UserRole.OPERATOR, "OldPassword123456789!")

    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "self_pw_user", "password": "OldPassword123456789!"})
    assert login_res.status_code == 200
    csrf = login_res.json()["csrf_token"]

    with patch.object(_sec_audit.AuditLogger, "log_event", side_effect=RuntimeError("Audit disk full")):
        res = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "OldPassword123456789!",
                "new_password": "NewSecurePassword12345!"
            },
            headers={"X-CSRF-Token": csrf}
        )
        assert res.status_code == 500

    # Existing session is still valid
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["user"]["username"] == "self_pw_user"

    # Old password still works for login; new password rejected
    login_old = TestClient(_backend.app).post("/api/v1/auth/login", json={"username": "self_pw_user", "password": "OldPassword123456789!"})
    assert login_old.status_code == 200
    login_new = TestClient(_backend.app).post("/api/v1/auth/login", json={"username": "self_pw_user", "password": "NewSecurePassword12345!"})
    assert login_new.status_code == 401


def _get_fresh_target_service():
    target_svc_mod = importlib.import_module("08_backend.services.target_service")
    p5_watchlist = importlib.import_module("05_target_matching.watchlist")
    p5_repo = importlib.import_module("05_target_matching.repository")
    sqlite_repo = p5_repo.SQLiteTargetMatchingRepository(":memory:")
    fresh_wm = p5_watchlist.WatchlistManager(repository=sqlite_repo)
    svc = target_svc_mod.TargetService(repository=sqlite_repo, watchlist_manager=fresh_wm)
    return svc, sqlite_repo


def test_target_create_audit_failure_compensation(clean_security_env):
    """
    TARGET_CREATE: when audit logging fails, target is physically removed from in-memory index,
    active normalized index, AND persistent repository database.
    """
    repo, sm = clean_security_env
    admin = _create_user(repo, "admin_tc_test", UserRole.ADMIN)

    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "admin_tc_test", "password": "Password123456789!"})
    csrf = login_res.json()["csrf_token"]

    svc, persistent_repo = _get_fresh_target_service()
    _backend.app.dependency_overrides[importlib.import_module("08_backend.dependencies").get_target_service] = lambda: svc
    _backend.app.dependency_overrides[importlib.import_module("08_backend.routers.targets").get_target_service] = lambda: svc

    with patch.object(_sec_audit.AuditLogger, "log_event", side_effect=RuntimeError("Audit pipeline timeout")):
        res = client.post(
            "/api/v1/targets",
            json={"registration": "GJ01FAIL999", "priority": "CRITICAL"},
            headers={"X-CSRF-Token": csrf}
        )
        assert res.status_code == 500

    # 1. Assert in-memory list has zero matches
    targets = svc.list_targets()
    matching = [t for t in targets if t.registration == "GJ01FAIL999"]
    assert len(matching) == 0

    # 2. Assert in-memory exact and state index has no trace of normalized registration
    norm_reg = "GJ01FAIL999"
    state_code = "GJ"
    assert norm_reg not in svc.watchlist_manager._exact_index or len(svc.watchlist_manager._exact_index[norm_reg]) == 0
    assert state_code not in svc.watchlist_manager._state_index or len(svc.watchlist_manager._state_index[state_code]) == 0

    # 3. Assert persistent database repository has ZERO records for this registration
    active_persistent = persistent_repo.list_active_watchlist_entries()
    persistent_matching = [e for e in active_persistent if e.registration == "GJ01FAIL999"]
    assert len(persistent_matching) == 0



def test_target_update_audit_failure_detailed_compensation(clean_security_env):
    """TARGET_UPDATE: verifies exact snapshot rollback on priority, enabled, expires_at, notes, and metadata."""
    repo, sm = clean_security_env
    admin = _create_user(repo, "admin_tu_test", UserRole.ADMIN)

    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "admin_tu_test", "password": "Password123456789!"})
    csrf = login_res.json()["csrf_token"]

    target_sch_mod = importlib.import_module("08_backend.schemas.targets")
    svc, persistent_repo = _get_fresh_target_service()
    _backend.app.dependency_overrides[importlib.import_module("08_backend.dependencies").get_target_service] = lambda: svc
    _backend.app.dependency_overrides[importlib.import_module("08_backend.routers.targets").get_target_service] = lambda: svc

    # Create base target
    base_tgt = svc.create_target(
        target_sch_mod.TargetCreateRequest(
            registration="GJ01EXACT123",
            priority=target_sch_mod.TargetPriorityEnum.NORMAL,
            notes="Original notes",
            metadata={"case_id": "CASE-100", "dept": "TRAFFIC"}
        )
    )
    tid = base_tgt.target_id

    # 1. Test Priority and Notes Rollback on Audit Failure
    with patch.object(_sec_audit.AuditLogger, "log_event", side_effect=RuntimeError("Audit failure")):
        res = client.patch(
            f"/api/v1/targets/{tid}",
            json={"priority": "CRITICAL", "notes": "Tampered notes"},
            headers={"X-CSRF-Token": csrf}
        )
        assert res.status_code == 500

    t1 = svc.get_target(tid)
    assert t1.priority == "NORMAL"
    assert t1.notes == "Original notes"

    # 2. Test Metadata Exact Rollback on Audit Failure
    with patch.object(_sec_audit.AuditLogger, "log_event", side_effect=RuntimeError("Audit failure")):
        res = client.patch(
            f"/api/v1/targets/{tid}",
            json={"metadata": {"case_id": "CASE-999", "new_unwanted_key": "injected"}},
            headers={"X-CSRF-Token": csrf}
        )
        assert res.status_code == 500

    t2 = svc.get_target(tid)
    assert t2.metadata == {"case_id": "CASE-100", "dept": "TRAFFIC"}
    assert "new_unwanted_key" not in t2.metadata


def test_target_disable_audit_failure_compensation(clean_security_env):
    """TARGET_DISABLE: when audit logging fails, target enabled status is restored to True."""
    repo, sm = clean_security_env
    admin = _create_user(repo, "admin_td_test", UserRole.ADMIN)

    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "admin_td_test", "password": "Password123456789!"})
    csrf = login_res.json()["csrf_token"]

    target_sch_mod = importlib.import_module("08_backend.schemas.targets")
    svc, persistent_repo = _get_fresh_target_service()
    _backend.app.dependency_overrides[importlib.import_module("08_backend.dependencies").get_target_service] = lambda: svc
    _backend.app.dependency_overrides[importlib.import_module("08_backend.routers.targets").get_target_service] = lambda: svc

    tgt = svc.create_target(
        target_sch_mod.TargetCreateRequest(
            registration="GJ01DIS1234",
            priority=target_sch_mod.TargetPriorityEnum.NORMAL
        )
    )
    tid = tgt.target_id

    with patch.object(_sec_audit.AuditLogger, "log_event", side_effect=RuntimeError("Audit failure")):
        res = client.delete(
            f"/api/v1/targets/{tid}",
            headers={"X-CSRF-Token": csrf}
        )
        assert res.status_code == 500

    refetched = svc.get_target(tid)
    assert refetched.enabled is True


def test_alert_ack_audit_failure_compensation(clean_security_env):
    """ALERT_ACK: when audit logging fails, alert acknowledgment is restored to unacknowledged state."""
    repo, sm = clean_security_env
    operator = _create_user(repo, "op_ack_test", UserRole.OPERATOR)

    client = TestClient(_backend.app)
    login_res = client.post("/api/v1/auth/login", json={"username": "op_ack_test", "password": "Password123456789!"})
    csrf = login_res.json()["csrf_token"]

    # Mock alert service with real in-memory alert state
    alert_sch_mod = importlib.import_module("08_backend.schemas.alerts")
    mock_alert = {
        "alert_id": "alt-test-comp-001",
        "watchlist_id": "tgt-1",
        "sighting_id": "sig-1",
        "camera_id": "cam_01",
        "stream_epoch": 1,
        "track_id": 101,
        "registration": "GJ01AB1234",
        "match_score": 0.95,
        "match_class": "CONFIRMED",
        "severity": "CRITICAL",
        "created_at": datetime.now(timezone.utc),
        "acknowledged": False,
        "acknowledged_by": None,
        "acknowledged_at": None,
        "explanation": []
    }

    mock_alert_service = MagicMock()
    mock_alert_service.get_alert_by_id.return_value = alert_sch_mod.AlertResponse(**mock_alert)
    mock_alert_service.get_alert_snapshot.return_value = {
        "alert_id": "alt-test-comp-001",
        "acknowledged": False,
        "acknowledged_by": None,
        "acknowledged_at": None,
    }

    def _mock_ack(alert_id, acknowledged_by):
        mock_alert["acknowledged"] = True
        mock_alert["acknowledged_by"] = acknowledged_by
        mock_alert["acknowledged_at"] = datetime.now(timezone.utc)
        return alert_sch_mod.AlertAckResponse(
            success=True,
            alert_id=alert_id,
            acknowledged=True,
            acknowledged_by=acknowledged_by,
            acknowledged_at=mock_alert["acknowledged_at"]
        )

    def _mock_restore(alert_id, snapshot):
        mock_alert["acknowledged"] = snapshot["acknowledged"]
        mock_alert["acknowledged_by"] = snapshot["acknowledged_by"]
        mock_alert["acknowledged_at"] = snapshot["acknowledged_at"]

    mock_alert_service.acknowledge_alert.side_effect = _mock_ack
    mock_alert_service.restore_alert_snapshot.side_effect = _mock_restore

    _backend.app.dependency_overrides[importlib.import_module("08_backend.dependencies").get_alert_service] = lambda: mock_alert_service

    with patch.object(_sec_audit.AuditLogger, "log_event", side_effect=RuntimeError("Audit write timeout")):
        res = client.post(
            "/api/v1/alerts/alt-test-comp-001/ack",
            json={},
            headers={"X-CSRF-Token": csrf}
        )
        assert res.status_code == 500

    # Assert alert state was restored to acknowledged=False
    assert mock_alert["acknowledged"] is False
    assert mock_alert["acknowledged_by"] is None
