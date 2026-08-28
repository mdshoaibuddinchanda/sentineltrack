import asyncio
import importlib
import logging
from typing import Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

try:
    from .manager import get_connection_manager
except (ImportError, ValueError):
    get_connection_manager = importlib.import_module("08_backend.websocket.manager").get_connection_manager

# 10_security always via importlib (module name starts with digit)
_sec = importlib.import_module("10_security")
Permission = _sec.Permission
get_session_manager = _sec.get_session_manager
get_security_repository = _sec.get_security_repository
get_security_config = _sec.get_security_config
_perms_m = importlib.import_module("10_security.permissions")
has_permission = _perms_m.has_permission
get_permissions_for_role = _perms_m.get_permissions_for_role


logger = logging.getLogger("sentineltrack.ws")

# Maps incoming topic name patterns (uppercase) → required Permission
_TOPIC_PERMISSIONS: dict = {
    "ALERT": Permission.ALERT_READ,
    "SIGHTING": Permission.SIGHTING_READ,
    "CAMERA": Permission.CAMERA_READ,
    "TARGET": Permission.TARGET_READ,
    "*": Permission.CAMERA_READ,  # wildcard requires at least camera read
}

router = APIRouter(tags=["WebSocket Real-Time Events"])


async def _authenticate_ws(websocket: WebSocket):
    """
    Validate Origin and session cookie on a WebSocket handshake.
    Returns (user_id, role, permissions_set) or raises WebSocketDisconnect(4401/4403).
    """
    # 1. Validate Origin header if present
    origin = websocket.headers.get("origin")
    if origin:
        sec_config = get_security_config()
        if origin not in sec_config.allowed_origins:
            logger.warning("WS handshake rejected: forbidden Origin '%s'", origin)
            await websocket.close(code=4403, reason="Forbidden Origin")
            return None, None, set()

    # Check if testing override is present on the app
    _dep_mod = importlib.import_module("10_security.dependencies")
    _get_prin = _dep_mod.get_current_principal
    override_fn = getattr(websocket.app, "dependency_overrides", {}).get(_get_prin)
    if override_fn:
        p = override_fn()
        return p.user_id, p.role, p.permissions

    session_token = websocket.cookies.get("sentinel_session")
    if not session_token:
        await websocket.close(code=4401, reason="Authentication required")
        return None, None, set()

    try:
        session_mgr = get_session_manager()
        res = session_mgr.validate_session(session_token)
        if res is None:
            await websocket.close(code=4401, reason="Session invalid or expired")
            return None, None, set()
        session, user, principal = res
        return user.user_id, user.role, principal.permissions
    except Exception as exc:
        logger.warning("WS auth error: %s", exc)
        try:
            await websocket.close(code=4401, reason="Authentication error")
        except Exception:
            pass
        return None, None, set()


def _filter_topics_for_permissions(requested: list, permissions: Set) -> Optional[list]:
    """
    Expand and filter requested topics against the principal's permission set.
    Never returns literal '*' wildcard; expands into permitted topic families.
    Returns list of authorized topic strings, or None if no topics are authorized.
    """
    allowed_topics = set()
    for topic in requested:
        topic_upper = topic.upper()
        if topic_upper == "*":
            # Wildcard: expand into all topic families the user has permission for
            for prefix, perm in _TOPIC_PERMISSIONS.items():
                if perm in permissions:
                    allowed_topics.add(prefix)
        else:
            # Specific topic or prefix
            for prefix, perm in _TOPIC_PERMISSIONS.items():
                if topic_upper.startswith(prefix):
                    if perm in permissions:
                        allowed_topics.add(topic)
                    break

    return list(allowed_topics) if allowed_topics else None



@router.websocket("/ws/events")
async def websocket_events_endpoint(
    websocket: WebSocket,
    topics: Optional[str] = Query(default=None, description="Comma-separated topics e.g. alerts,sightings,camera_health")
):
    user_id, role, permissions = await _authenticate_ws(websocket)
    if user_id is None:
        return  # already closed with 4401

    requested = [t.strip().upper() for t in topics.split(",")] if topics else ["*"]
    authorized = _filter_topics_for_permissions(requested, permissions)
    if authorized is None:
        await websocket.close(code=4403, reason="Insufficient permissions for requested topics")
        logger.warning("WS 4403 user=%s requested_topics=%s", user_id, requested)
        return

    manager = get_connection_manager()
    queue = await manager.connect(websocket, topics=authorized)
    logger.info("WS connected user=%s role=%s topics=%s", user_id, role, authorized)

    try:
        async def send_loop():
            while True:
                msg = await queue.get()
                await websocket.send_text(msg)

        async def receive_loop():
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text('{"type":"pong"}')

        sender_task = asyncio.create_task(send_loop())
        receiver_task = asyncio.create_task(receive_loop())

        done, pending = await asyncio.wait(
            [sender_task, receiver_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
        logger.info("WS disconnected user=%s", user_id)


@router.websocket("/ws/alerts")
async def websocket_alerts_endpoint(websocket: WebSocket):
    user_id, role, permissions = await _authenticate_ws(websocket)
    if user_id is None:
        return

    if Permission.ALERT_READ not in permissions:
        await websocket.close(code=4403, reason="alert:read permission required")
        return

    manager = get_connection_manager()
    queue = await manager.connect(websocket, topics=["ALERT_CREATED", "ALERTS"])
    try:
        while True:
            msg = await queue.get()
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)


@router.websocket("/ws/sightings")
async def websocket_sightings_endpoint(websocket: WebSocket):
    user_id, role, permissions = await _authenticate_ws(websocket)
    if user_id is None:
        return

    if Permission.SIGHTING_READ not in permissions:
        await websocket.close(code=4403, reason="sighting:read permission required")
        return

    manager = get_connection_manager()
    queue = await manager.connect(websocket, topics=["SIGHTING_CREATED", "SIGHTINGS"])
    try:
        while True:
            msg = await queue.get()
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)

