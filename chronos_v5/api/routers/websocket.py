from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from chronos_v5.api.dependencies import get_api_key
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
