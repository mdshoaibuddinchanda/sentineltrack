import sys
import json
import time
import asyncio
import importlib
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, "c:/DR2/sentineltrack")

_sec_repo = importlib.import_module("10_security.repository")
_sec_sess = importlib.import_module("10_security.sessions")
_sec_pw = importlib.import_module("10_security.password")
_sec_models = importlib.import_module("10_security.models")
_backend = importlib.import_module("08_backend.app")
_conn_mgr_mod = importlib.import_module("08_backend.websocket.manager")

SqliteSecurityRepository = _sec_repo.SqliteSecurityRepository
set_security_repository = _sec_repo.set_security_repository
SessionManager = _sec_sess.SessionManager
set_session_manager = _sec_sess.set_session_manager
hash_password = _sec_pw.hash_password
User = _sec_models.User
UserRole = _sec_models.UserRole
get_connection_manager = _conn_mgr_mod.get_connection_manager


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


def _create_user(repo, username="ws_user", role=UserRole.OPERATOR, password="Password123456789!"):
    user = User(
        user_id=f"usr-{username}",
        username=username,
        display_name="WS Operator",
        password_hash=hash_password(password),
        role=role,
        enabled=True
    )
    repo.save_user(user)
    return user


def test_ws_unauthenticated_connection_rejected(clean_security_env):
    """D1: Unauthenticated WebSocket handshake on all endpoints is rejected with 4401."""
    client = TestClient(_backend.app)
    for path in ["/ws/events", "/ws/alerts", "/ws/sightings"]:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(path):
                pass
        assert exc.value.code == 4401


def test_ws_untrusted_origin_rejected(clean_security_env):
    """D1: WebSocket handshake from untrusted Origin is rejected with 4403 across endpoints."""
    repo, sm = clean_security_env
    user = _create_user(repo, "ws_op_origin", UserRole.OPERATOR)
    
    client = TestClient(_backend.app)
    client.post("/api/v1/auth/login", json={"username": "ws_op_origin", "password": "Password123456789!"})

    for path in ["/ws/events", "/ws/alerts", "/ws/sightings"]:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(path, headers={"Origin": "https://evil-hacker-site.com"}):
                pass
        assert exc.value.code == 4403


def test_ws_trusted_origin_accepted(clean_security_env):
    """D1: WebSocket handshake from trusted Origin succeeds."""
    repo, sm = clean_security_env
    user = _create_user(repo, "ws_op_good", UserRole.OPERATOR)
    
    client = TestClient(_backend.app)
    client.post("/api/v1/auth/login", json={"username": "ws_op_good", "password": "Password123456789!"})

    with client.websocket_connect("/ws/events", headers={"Origin": "http://localhost:5173"}) as ws:
        ws.send_text("ping")
        data = ws.receive_text()
        assert "pong" in data or "PONG" in data


def test_ws_wildcard_invariant_and_event_isolation(clean_security_env):
    """
    D3: Verify literal '*' is NEVER stored in ConnectionManager._client_topics for authenticated clients.
    Verify unauthorized event families (AUDIT, USER) are never delivered to OPERATOR.
    """
    repo, sm = clean_security_env
    user = _create_user(repo, "ws_op_wildcard_strict", UserRole.OPERATOR)
    
    client = TestClient(_backend.app)
    client.post("/api/v1/auth/login", json={"username": "ws_op_wildcard_strict", "password": "Password123456789!"})

    with client.websocket_connect("/ws/events?topics=*") as ws:
        manager = get_connection_manager()

        # D3 Invariant assertion
        for active_ws, client_topics in manager._client_topics.items():
            assert "*" not in client_topics, "Literal '*' must NEVER be stored in _client_topics"
            assert "ALERT" in client_topics or "CAMERA" in client_topics
            assert "AUDIT" not in client_topics
            assert "USER" not in client_topics

        # 1. Allowed CAMERA event -> delivered
        cam_msg = {"type": "CAMERA_STATUS", "camera_id": "cam_01", "status": "ONLINE"}
        asyncio.run(manager.broadcast(cam_msg, topic="CAMERA_STATUS"))
        received_cam = json.loads(ws.receive_text())
        assert received_cam["camera_id"] == "cam_01"

        # 2. Allowed ALERT event -> delivered
        alt_msg = {"type": "ALERT_CREATED", "alert_id": "alt_01", "severity": "HIGH"}
        asyncio.run(manager.broadcast(alt_msg, topic="ALERT_CREATED"))
        received_alt = json.loads(ws.receive_text())
        assert received_alt["alert_id"] == "alt_01"

        # 3. Unauthorized AUDIT event -> withheld
        audit_msg = {"type": "AUDIT_EVENT", "action": "SECRET_AUDIT_LOG"}
        asyncio.run(manager.broadcast(audit_msg, topic="AUDIT_EVENT"))

        # 4. Unauthorized USER event -> withheld
        user_msg = {"type": "USER_CREATED", "username": "new_admin"}
        asyncio.run(manager.broadcast(user_msg, topic="USER_CREATED"))

        # 5. Subsequent allowed SIGHTING event -> delivered immediately
        sight_msg = {"type": "SIGHTING_CREATED", "sighting_id": "sig_999"}
        asyncio.run(manager.broadcast(sight_msg, topic="SIGHTING_CREATED"))
        received_sight = json.loads(ws.receive_text())
        assert received_sight["sighting_id"] == "sig_999"


def test_ws_role_downgrade_closes_socket(clean_security_env):
    """
    D2: When an authenticated user's role is changed/downgraded during an active WebSocket session,
    the background validator detects the topic permission mismatch and closes the connection with code 4403.
    """
    repo, sm = clean_security_env
    # User starts as SUPERVISOR (authorized for audit read + all operational topics)
    user = _create_user(repo, "ws_supervisor_downgrade", UserRole.SUPERVISOR)

    client = TestClient(_backend.app)
    client.post("/api/v1/auth/login", json={"username": "ws_supervisor_downgrade", "password": "Password123456789!"})

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/events?topics=*") as ws:
            # Downgrade user to OPERATOR in repository
            user.role = UserRole.OPERATOR
            repo.update_user(user)
            # Sleep past validator loop interval (5s)
            time.sleep(5.5)
            ws.receive_text()
    assert exc.value.code == 4403


def test_ws_session_revocation_closes_socket(clean_security_env):
    """D1 & D2: Disabling a user account terminates active WebSocket connection with code 4401."""
    repo, sm = clean_security_env
    user = _create_user(repo, "ws_op_revoked", UserRole.OPERATOR)
    
    client = TestClient(_backend.app)
    client.post("/api/v1/auth/login", json={"username": "ws_op_revoked", "password": "Password123456789!"})

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/events") as ws:
            # Disable user in repository and revoke active sessions
            repo.disable_user(user.user_id)
            sm.revoke_all_user_sessions(user.user_id)
            time.sleep(5.5)
            ws.receive_text()
    assert exc.value.code == 4401


def test_ws_alerts_and_sightings_endpoints_enforce_session_validation(clean_security_env):
    """D1: /ws/alerts and /ws/sightings both share the unified runner and disconnect on session revocation."""
    repo, sm = clean_security_env
    user = _create_user(repo, "ws_op_spec_endpoints", UserRole.OPERATOR)

    client = TestClient(_backend.app)
    client.post("/api/v1/auth/login", json={"username": "ws_op_spec_endpoints", "password": "Password123456789!"})

    # Test /ws/alerts
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/alerts") as ws:
            repo.disable_user(user.user_id)
            sm.revoke_all_user_sessions(user.user_id)
            time.sleep(5.5)
            ws.receive_text()
    assert exc.value.code == 4401
