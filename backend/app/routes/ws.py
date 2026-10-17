# WebSocket /ws/matches/{match_id}: server pushes match_updated / showcase_updated; client messages ignored.
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime import manager

router = APIRouter()


@router.websocket("/ws/matches/{match_id}")
async def match_socket(ws: WebSocket, match_id: str):
    await manager.connect(match_id, ws)
    try:
        while True:
            await ws.receive_text()  # keep the connection open; content is ignored
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(match_id, ws)
