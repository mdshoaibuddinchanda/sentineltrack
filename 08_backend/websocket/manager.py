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
        self._client_loops: Dict[WebSocket, asyncio.AbstractEventLoop] = {}
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
            self._client_loops[websocket] = asyncio.get_running_loop()
            self.metrics.set_ws_clients(len(self._active_connections))
        return client_queue


    async def disconnect(self, websocket: WebSocket):
        with self._lock:
            if websocket in self._active_connections:
                del self._active_connections[websocket]
            if websocket in self._client_topics:
                del self._client_topics[websocket]
            if websocket in self._client_loops:
                del self._client_loops[websocket]
            self.metrics.set_ws_clients(len(self._active_connections))

    async def _on_bus_event(self, event: BaseEvent):
        """Dispatches event from event bus to matching connected WebSocket clients."""
        await self.broadcast({
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "data": event.payload
        }, topic=event.event_type)

    @staticmethod
    def _enqueue_message(queue: asyncio.Queue, text_payload: str) -> None:
        """Put a message into a client queue using only its owning event loop."""
        try:
            queue.put_nowait(text_payload)
        except asyncio.QueueFull:
            # Slow client backpressure drop policy: retain the newest event.
            try:
                queue.get_nowait()
                queue.put_nowait(text_payload)
            except Exception:
                pass

    async def broadcast(self, message: Dict[str, Any], topic: str = "*"):
        """Non-blocking broadcast that is safe across publisher/client event loops."""
        with self._lock:
            targets = list(self._active_connections.items())
            client_topics = dict(self._client_topics)
            client_loops = dict(self._client_loops)

        text_payload = json.dumps(message)

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        for ws, q in targets:
            sub_topics = client_topics.get(ws, set())
            matches = "*" in sub_topics
            if not matches:
                top_up = topic.upper()
                for st in sub_topics:
                    s_up = st.upper()
                    if s_up == top_up or s_up in top_up or top_up in s_up or s_up.rstrip("S") in top_up:
                        matches = True
                        break

            if matches:
                owner_loop = client_loops.get(ws)
                if owner_loop and owner_loop is not current_loop and not owner_loop.is_closed():
                    # asyncio.Queue becomes loop-affine when a consumer waits.
                    # Schedule the bounded put on the ASGI/TestClient loop.
                    owner_loop.call_soon_threadsafe(self._enqueue_message, q, text_payload)
                else:
                    self._enqueue_message(q, text_payload)

    def get_client_count(self) -> int:
        return len(self._active_connections)


_GLOBAL_WS_MANAGER: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    global _GLOBAL_WS_MANAGER
    if _GLOBAL_WS_MANAGER is None:
        cfg = get_backend_config().websocket
        _GLOBAL_WS_MANAGER = ConnectionManager(queue_size=cfg.client_queue_size)
    return _GLOBAL_WS_MANAGER
