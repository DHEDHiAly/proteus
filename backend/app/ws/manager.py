import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket):
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = set()
        self.active_connections[run_id].add(websocket)
        logger.info(f"WebSocket connected for run {run_id}")

    def disconnect(self, run_id: str, websocket: WebSocket):
        if run_id in self.active_connections:
            self.active_connections[run_id].discard(websocket)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]
        logger.info(f"WebSocket disconnected for run {run_id}")

    async def broadcast(self, run_id: str, message: dict):
        if run_id not in self.active_connections:
            return
        disconnected = set()
        for websocket in self.active_connections[run_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.add(websocket)
        for ws in disconnected:
            self.active_connections[run_id].discard(ws)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]


ws_manager = WebSocketManager()
