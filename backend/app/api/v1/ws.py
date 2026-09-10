"""
WebSocket Endpoint — Real-time live feed updates for Dashboard & Supervisor Command.

Authentication
--------------
This socket carries live traveller telemetry (names, document numbers, risk
verdicts, criminal flags). It previously accepted every connection with no
credentials whatsoever, so anyone who could reach the host could subscribe to the
entire border feed.

Browsers cannot set headers on a WebSocket handshake, so the application JWT is
passed as the `token` query parameter (`wss://host/api/v1/ws?token=<jwt>`) and
validated before `accept()`. Unauthenticated peers are closed with 1008.
"""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSockets"])

# Only these roles may observe the live operational feed.
FEED_ROLES = {"officer", "supervisor", "admin", "investigator"}


def _authenticate(token: Optional[str]) -> Optional[User]:
    """Resolves a JWT to an active, approved user, or None."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active or not user.is_approved:
            return None
        if user.role not in FEED_ROLES:
            return None
        # Detach the values we need so the session can close immediately.
        db.expunge(user)
        return user
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("WebSocket auth lookup failed: %s", exc)
        return None
    finally:
        db.close()


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
        # Iterate over a copy: failed sockets are removed during the loop.
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
):
    """Authenticated real-time dashboard telemetry and scan notifications."""
    user = _authenticate(token)
    if user is None:
        # Reject before accept() so no telemetry is ever sent to an anonymous peer.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "connection_established",
            "message": "Connected to Border Guard Real-Time Event Stream",
            "role": user.role,
        })
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("WebSocket closed unexpectedly: %s", exc)
        manager.disconnect(websocket)
