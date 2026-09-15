"""WebSocket connection manager for live API clients."""

import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger("ws_manager")


class WebSocketManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._active_recording_sid: str | None = None

    def set_recording_session(self, sid: str | None):
        """Track UI recording state without binding the API to hardware ingestion."""
        self._active_recording_sid = sid
        if sid:
            logger.info("Recording session marked active: %s", sid)
        else:
            logger.info("Recording session cleared")

    async def _broadcast(self, sid: str, message: str):
        disconnected = set()
        for ws in self._connections.get(sid, []):
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)
        self._connections[sid] -= disconnected

    async def connect(self, sid: str, websocket: WebSocket):
        await websocket.accept()
        self._connections[sid].add(websocket)

    async def disconnect(self, sid: str, websocket: WebSocket):
        self._connections[sid].discard(websocket)


ws_manager = WebSocketManager()
