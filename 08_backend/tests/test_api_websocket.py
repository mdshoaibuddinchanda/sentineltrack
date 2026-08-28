import json
import pytest
import importlib
from fastapi.testclient import TestClient

backend_app = importlib.import_module("08_backend.app")
ws_mgr_mod = importlib.import_module("08_backend.websocket.manager")
event_bus_mod = importlib.import_module("08_backend.event_bus")

app = backend_app.app
AlertCreatedEvent = event_bus_mod.AlertCreatedEvent
get_event_bus = event_bus_mod.get_event_bus


def test_websocket_connect_and_ping_pong():
    client = TestClient(app)
    with client.websocket_connect("/ws/events") as ws:
        ws.send_text("ping")
        resp = ws.receive_text()
        data = json.loads(resp)
        assert data["type"] == "pong"


def test_websocket_alert_broadcast():
    client = TestClient(app)
    bus = get_event_bus()

    with client.websocket_connect("/ws/alerts") as ws:
        # Publish event on bus
        import asyncio
        asyncio.run(bus.publish(AlertCreatedEvent(payload={
            "alert_id": "ws_test_alert_01",
            "camera_id": "cam_01",
            "registration": "GJ01WS9999",
            "severity": "CRITICAL"
        })))

        msg = ws.receive_text()
        data = json.loads(msg)
        assert data["event_type"] == "ALERT_CREATED"
        assert data["data"]["alert_id"] == "ws_test_alert_01"
        assert data["data"]["registration"] == "GJ01WS9999"


def test_connection_manager_backpressure_and_drop():
    manager = ws_mgr_mod.ConnectionManager(queue_size=2)
    # Simulate queue drop
    import asyncio
    queue = asyncio.Queue(maxsize=2)
    manager._active_connections["dummy_ws"] = queue
    manager._client_topics["dummy_ws"] = {"*"}

    # Broadcast 5 messages
    for i in range(5):
        asyncio.run(manager.broadcast({"msg": i}, topic="TEST"))

    assert queue.qsize() == 2
    # Verify oldest dropped and newest present: 3, 4
    m1 = json.loads(asyncio.run(queue.get()))
    m2 = json.loads(asyncio.run(queue.get()))
    assert m1["msg"] == 3
    assert m2["msg"] == 4
