import asyncio
import json
import logging
import threading
from typing import Dict, List, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect

try:
    from ..config import get_backend_config
    from ..event_bus import get_event_bus, BaseEvent
    from ..metrics import get_metrics_collector
except (ImportError, ValueError):
    import importlib
    get_backend_config = importlib.import_module("08_backend.config").get_backend_config
    ev_m = importlib.import_module("08_backend.event_bus")
    get_event_bus, BaseEvent = ev_m.get_event_bus, ev_m.BaseEvent
    get_metrics_collector = importlib.import_module("08_backend.metrics").get_metrics_collector

logger = logging.getLogger("sentineltrack.websocket")


class ConnectionManager:
    """
    Manages active WebSocket connections, topic routing, and per-client bounded queues.
    Prevents slow clients from causing backend backpressure or memory leaks.
    """

    def __init__(self, queue_size: int = 100):
        self.queue_size = queue_size
        self._active_connections: Dict[WebSocket, asyncio.Queue] = {}
        self._client_topics: Dict[WebSocket, Set[str]] = {}
        # ConnectionManager is global and can be touched by the ASGI event
        # loop as well as synchronous test/integration callers that execute
        # broadcast() through another loop.  The protected sections below do
        # not await, so a thread lock avoids binding shared state to one loop.
        self._lock = threading.RLock()
        self.metrics = get_metrics_collector()

        # Connect to global event bus
        bus = get_event_bus()
        bus.subscribe_all(self._on_bus_event)

    async def connect(self, websocket: WebSocket, topics: Optional[List[str]] = None) -> asyncio.Queue:
        await websocket.accept()
        client_queue: asyncio.Queue = asyncio.Queue(maxsize=self.queue_size)
        # Structural Invariant: literal "*" can NEVER enter client subscriptions
        sanitized_topics = {t.upper() for t in (topics or []) if t != "*"}
        with self._lock:
            self._active_connections[websocket] = client_queue
            self._client_topics[websocket] = sanitized_topics
            self.metrics.set_ws_clients(len(self._active_connections))
        return client_queue


    async def disconnect(self, websocket: WebSocket):
        with self._lock:
            if websocket in self._active_connections:
                del self._active_connections[websocket]
            if websocket in self._client_topics:
                del self._client_topics[websocket]
            self.metrics.set_ws_clients(len(self._active_connections))

    async def _on_bus_event(self, event: BaseEvent):
        """Dispatches event from event bus to matching connected WebSocket clients."""
        await self.broadcast({
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "data": event.payload
        }, topic=event.event_type)

    async def broadcast(self, message: Dict[str, Any], topic: str = "*"):
        """Non-blocking broadcast to all subscribed clients. Drops message if client queue is full."""
        with self._lock:
            targets = list(self._active_connections.items())

        text_payload = json.dumps(message)

        for ws, q in targets:
            sub_topics = self._client_topics.get(ws, set())
            matches = "*" in sub_topics
            if not matches:
                top_up = topic.upper()
                for st in sub_topics:
                    s_up = st.upper()
                    if s_up == top_up or s_up in top_up or top_up in s_up or s_up.rstrip("S") in top_up:
                        matches = True
                        break

            if matches:
                try:
                    q.put_nowait(text_payload)
                except asyncio.QueueFull:
                    # Slow client backpressure drop policy
                    try:
                        q.get_nowait()
                        q.put_nowait(text_payload)
                    except Exception:
                        pass

    def get_client_count(self) -> int:
        return len(self._active_connections)


_GLOBAL_WS_MANAGER: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    global _GLOBAL_WS_MANAGER
    if _GLOBAL_WS_MANAGER is None:
        cfg = get_backend_config().websocket
        _GLOBAL_WS_MANAGER = ConnectionManager(queue_size=cfg.client_queue_size)
    return _GLOBAL_WS_MANAGER
