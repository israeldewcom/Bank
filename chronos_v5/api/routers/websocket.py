# chronos_v5/api/routers/websocket.py
# SECURITY FIX: get_api_key was imported but never actually applied as a
# dependency, so /ws/market accepted any unauthenticated connection. It is
# now checked before websocket.accept() is called.
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from chronos_v5.config import Config
from chronos_v5.nigeria_adapter import nigeria
import json, asyncio
from datetime import datetime
from chronos_v5.logger_setup import logger

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

@router.websocket("/market")
async def websocket_market(websocket: WebSocket):
    api_key = websocket.headers.get("X-API-Key") or websocket.query_params.get("api_key")
    if api_key != Config.API_KEY:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket)
    try:
        while True:
            data = {
                "ngx_asi": nigeria.ngx_all_share,
                "mpr": nigeria.cbn_mpr,
                "ngn_usd": nigeria.ngn_usd_parallel,
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket disconnected")
