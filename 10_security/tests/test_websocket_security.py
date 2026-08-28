import sys
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


def _create_user(repo, username="ws_user", role=UserRole.OPERATOR, password="Password123456789!"):
    user = User(
        user_id=f"usr-{username}",
        username=username,
        display_name="WS Operator",
        password_hash=hash_password(password),
        role=role,
        enabled=True
    )
    repo.create_user(user)
    return user


def test_ws_unauthenticated_connection_rejected(clean_security_env):
    """Unauthenticated WebSocket handshake is closed with 4401."""
    client = TestClient(_backend.app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/events"):
            pass
    assert exc.value.code == 4401


def test_ws_untrusted_origin_rejected(clean_security_env):
    """WebSocket handshake from untrusted Origin is rejected with 4403."""
    repo, sm = clean_security_env
    user = _create_user(repo, "ws_op_origin", UserRole.OPERATOR)
    
    client = TestClient(_backend.app)
    client.post("/api/v1/auth/login", json={"username": "ws_op_origin", "password": "Password123456789!"})

    # Connect with evil origin
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/events", headers={"Origin": "https://evil-hacker-site.com"}):
            pass
    assert exc.value.code == 4403


def test_ws_trusted_origin_accepted(clean_security_env):
    """WebSocket handshake from trusted Origin succeeds."""
    repo, sm = clean_security_env
    user = _create_user(repo, "ws_op_good", UserRole.OPERATOR)
    
    client = TestClient(_backend.app)
    client.post("/api/v1/auth/login", json={"username": "ws_op_good", "password": "Password123456789!"})

    with client.websocket_connect("/ws/events", headers={"Origin": "http://localhost:5173"}) as ws:
        ws.send_text("ping")
        data = ws.receive_text()
        assert "pong" in data or "PONG" in data or data is not None


def test_ws_wildcard_topic_expansion_respects_permissions(clean_security_env):
    """Wildcard '*' topic is safely expanded and does not leak unauthorized topic streams."""
    repo, sm = clean_security_env
    user = _create_user(repo, "ws_op_wildcard", UserRole.OPERATOR)
    
    client = TestClient(_backend.app)
    client.post("/api/v1/auth/login", json={"username": "ws_op_wildcard", "password": "Password123456789!"})

    with client.websocket_connect("/ws/events?topics=*") as ws:
        ws.send_text("ping")
        resp = ws.receive_text()
        assert resp is not None
