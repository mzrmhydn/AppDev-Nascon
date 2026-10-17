# WebSocket connection manager per match_id + a thread-safe notify() (contract §2.14).
# Services run in threadpool threads while sockets live on the event loop, so notify() hands the
# broadcast to the loop. A broadcast failure must never fail the request that triggered it.
import asyncio
import logging

from fastapi import WebSocket

log = logging.getLogger("nascon")
LOOP = None  # set in main.py at startup


class ConnectionManager:
    def __init__(self):
        self.sockets = {}  # match_id -> set of WebSocket

    async def connect(self, match_id, ws: WebSocket):
        await ws.accept()
        self.sockets.setdefault(match_id, set()).add(ws)

    def disconnect(self, match_id, ws: WebSocket):
        self.sockets.get(match_id, set()).discard(ws)

    async def broadcast(self, match_id, message):
        for ws in list(self.sockets.get(match_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(match_id, ws)  # client went away


manager = ConnectionManager()


def notify(match_id, message):
    """Callable from any thread (or the loop itself)."""
    try:
        if LOOP is None:
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is LOOP:
            LOOP.create_task(manager.broadcast(match_id, message))
        else:
            asyncio.run_coroutine_threadsafe(manager.broadcast(match_id, message), LOOP)
    except Exception as exc:
        log.warning("broadcast for %s failed: %s", match_id, exc)
