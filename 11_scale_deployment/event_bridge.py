import os
import json
import time
import logging
import threading
import importlib
from typing import Dict, Any, Optional, Callable, Set
from collections import deque
import psycopg

logger = logging.getLogger("sentineltrack.event_bridge")

CHANNEL_NAME = "sentineltrack_events"


class PostgresEventBridge:
    """
    Split-process event transport connecting Analytics and API worker processes
    via PostgreSQL LISTEN/NOTIFY with dedicated persistent session and LRU deduplication.
    """

    def __init__(
        self,
        channel: str = CHANNEL_NAME,
        event_bus=None,
        dedup_history_size: int = 5000
    ):
        self.channel = channel
        if event_bus is not None:
            self.event_bus = event_bus
        else:
            try:
                ev_m = importlib.import_module("08_backend.event_bus")
                self.event_bus = ev_m.get_event_bus()
            except Exception:
                self.event_bus = None
        self.dedup_history_size = dedup_history_size


        self._recent_events: deque = deque(maxlen=dedup_history_size)
        self._recent_set: Set[str] = set()
        self._lock = threading.Lock()
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None

    def publish_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        Publishes a lightweight event notification to PostgreSQL NOTIFY channel.
        Does not put large blobs or secrets in payload.
        """
        event_id = payload.get("event_id") or payload.get("alert_id") or payload.get("sighting_id") or str(time.time())
        notification_data = {
            "event_id": event_id,
            "event_type": event_type,
            "camera_id": payload.get("camera_id"),
            "resource_id": payload.get("alert_id") or payload.get("sighting_id") or payload.get("target_id"),
            "timestamp": time.time()
        }

        try:
            db_m = importlib.import_module("00_foundation.registry.database")
            with db_m.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"NOTIFY {self.channel}, %s;",
                        (json.dumps(notification_data),)
                    )
                conn.commit()
            return True
        except Exception as e:
            logger.warning(f"Failed to publish PostgreSQL NOTIFY event: {e}")
            return False

    def start_listener(self) -> None:
        """Starts dedicated persistent connection listener for incoming PostgreSQL notifications."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._listener_thread = threading.Thread(
                target=self._listen_loop,
                daemon=True,
                name="PostgresEventBridgeListener"
            )
            self._listener_thread.start()
            logger.info(f"PostgresEventBridge listening on channel [{self.channel}]")

    def stop_listener(self) -> None:
        with self._lock:
            self._running = False
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=2.0)
            logger.info("PostgresEventBridge listener stopped.")

    def _listen_loop(self) -> None:
        backoff_s = 1.0

        while self._running:
            try:
                # Dedicated persistent connection for LISTEN (cannot use pooled transaction conn)
                db_m = importlib.import_module("00_foundation.registry.database")
                conn = db_m.get_connection()
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(f"LISTEN {self.channel};")

                logger.info(f"Dedicated connection subscribed to LISTEN {self.channel}")
                backoff_s = 1.0

                # Generator yielding Notify objects
                for notify in conn.notifies():
                    if not self._running:
                        break

                    try:
                        data = json.loads(notify.payload)
                        event_id = data.get("event_id")

                        # Deduplication check
                        with self._lock:
                            if event_id and event_id in self._recent_set:
                                continue
                            if event_id:
                                if len(self._recent_events) >= self.dedup_history_size:
                                    oldest = self._recent_events.popleft()
                                    self._recent_set.discard(oldest)
                                self._recent_events.append(event_id)
                                self._recent_set.add(event_id)

                        self._dispatch_local(data)
                    except Exception as e:
                        logger.error(f"Error handling NOTIFY payload: {e}")

                conn.close()

            except Exception as e:
                if self._running:
                    logger.warning(f"LISTEN connection interrupted: {e}. Reconnecting in {backoff_s}s...")
                    time.sleep(backoff_s)
                    backoff_s = min(30.0, backoff_s * 1.5)

    def _dispatch_local(self, data: Dict[str, Any]) -> None:
        """Dispatches bridged notification to local EventBus for WebSocket propagation."""
        if not self.event_bus:
            return

        event_type = data.get("event_type")
        payload = data

        try:
            ev_m = importlib.import_module("08_backend.event_bus")
            if event_type == "ALERT_CREATED":
                self.event_bus.publish_sync(ev_m.AlertCreatedEvent(payload=payload))
            elif event_type == "SIGHTING_CREATED":
                self.event_bus.publish_sync(ev_m.SightingCreatedEvent(payload=payload))
        except Exception as e:
            logger.error(f"Error dispatching local event from bridge: {e}")



_GLOBAL_EVENT_BRIDGE: Optional[PostgresEventBridge] = None
_BRIDGE_LOCK = threading.Lock()


def get_event_bridge() -> PostgresEventBridge:
    global _GLOBAL_EVENT_BRIDGE
    with _BRIDGE_LOCK:
        if _GLOBAL_EVENT_BRIDGE is None:
            _GLOBAL_EVENT_BRIDGE = PostgresEventBridge()
        return _GLOBAL_EVENT_BRIDGE
