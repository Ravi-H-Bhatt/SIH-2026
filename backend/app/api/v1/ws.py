"""
WebSocket Endpoint — Real-time live feed updates for Dashboard & Supervisor Command.
"""

import json
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["WebSockets"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        payload = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket connection endpoint for real-time dashboard telemetry and scan notifications.
    """
    await manager.connect(websocket)
    try:
        # Send initial connection handshake
        await websocket.send_json({
            "type": "connection_established",
            "message": "Connected to Border Guard Real-Time Event Stream"
        })
        while True:
            # Keep connection open and handle incoming ping/messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
