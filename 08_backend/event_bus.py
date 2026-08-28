import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Set, Optional


@dataclass
class BaseEvent:
    event_type: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertCreatedEvent(BaseEvent):
    event_type: str = "ALERT_CREATED"


@dataclass
class SightingCreatedEvent(BaseEvent):
    event_type: str = "SIGHTING_CREATED"


@dataclass
class CameraHealthChangedEvent(BaseEvent):
    event_type: str = "CAMERA_HEALTH_CHANGED"


@dataclass
class RouteUpdatedEvent(BaseEvent):
    event_type: str = "ROUTE_UPDATED"


class AsyncEventBus:
    """In-memory async publish-subscribe event broker."""

    def __init__(self):
        self._subscribers: Dict[str, Set[Callable[[BaseEvent], Any]]] = {}
        self._global_subscribers: Set[Callable[[BaseEvent], Any]] = set()
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: str, handler: Callable[[BaseEvent], Any]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = set()
        self._subscribers[event_type].add(handler)

    def subscribe_all(self, handler: Callable[[BaseEvent], Any]):
        self._global_subscribers.add(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[BaseEvent], Any]):
        if event_type in self._subscribers:
            self._subscribers[event_type].discard(handler)
        self._global_subscribers.discard(handler)

    async def publish(self, event: BaseEvent):
        handlers: List[Callable[[BaseEvent], Any]] = list(self._global_subscribers)
        if event.event_type in self._subscribers:
            handlers.extend(self._subscribers[event.event_type])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                # Event handler failure must not crash event bus
                pass


_GLOBAL_EVENT_BUS: Optional[AsyncEventBus] = None


def get_event_bus() -> AsyncEventBus:
    global _GLOBAL_EVENT_BUS
    if _GLOBAL_EVENT_BUS is None:
        _GLOBAL_EVENT_BUS = AsyncEventBus()
    return _GLOBAL_EVENT_BUS
