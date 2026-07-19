from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from chronos_v5.settlement_execution import SettlementExecution
from chronos_v5.api.dependencies import get_api_key
from datetime import datetime, timezone

router = APIRouter()
executor = SettlementExecution()

class OrderRequest(BaseModel):
    trade_id: str
    side: str
    quantity: float
    price: float
    order_type: str = "LIMIT"

@router.post("/order", dependencies=[Depends(get_api_key)])
def place_order(order: OrderRequest):
    result = executor.send_order(order.trade_id, order.side, order.quantity, order.price, order.order_type)
    return result

@router.get("/orders", dependencies=[Depends(get_api_key)])
async def list_orders():
    # Return mock data – replace with real data when available
    return [
        {
            "id": "ORD-001",
            "pair": "EUR/USD",
            "side": "BUY",
            "amount": 1_200_000,
            "price": 1.0842,
            "status": "PENDING",
            "time": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": "ORD-002",
            "pair": "GBP/USD",
            "side": "SELL",
            "amount": 850_000,
            "price": 1.2678,
            "status": "FILLED",
            "time": datetime.now(timezone.utc).isoformat()
        }
    ]
