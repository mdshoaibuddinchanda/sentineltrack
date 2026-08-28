import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

try:
    from .manager import get_connection_manager
except (ImportError, ValueError):
    import importlib
    get_connection_manager = importlib.import_module("08_backend.websocket.manager").get_connection_manager

router = APIRouter(tags=["WebSocket Real-Time Events"])


@router.websocket("/ws/events")
async def websocket_events_endpoint(
    websocket: WebSocket,
    topics: Optional[str] = Query(default=None, description="Comma-separated topics e.g. alerts,sightings,camera_health")
):
    manager = get_connection_manager()
    topic_list = [t.strip().upper() for t in topics.split(",")] if topics else ["*"]
    queue = await manager.connect(websocket, topics=topic_list)

    try:
        # Sender task sends events from client queue to the websocket
        async def send_loop():
            while True:
                msg = await queue.get()
                await websocket.send_text(msg)

        # Receiver task listens for client pings/messages
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


@router.websocket("/ws/alerts")
async def websocket_alerts_endpoint(websocket: WebSocket):
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
