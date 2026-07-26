from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from chronos_v5.settlement_execution import SettlementExecution
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.repositories.trade_repository import TradeRepositoryAsync
from chronos_v5.models import User
from datetime import datetime, timezone

router = APIRouter()
executor = SettlementExecution()

class OrderRequest(BaseModel):
    trade_id: str
    side: str
    quantity: float
    price: float
    order_type: str = "LIMIT"

@router.post("/order")
async def place_order(order: OrderRequest, current_user: User = Depends(get_current_user)):
    repo = TradeRepositoryAsync()
    trade = await repo.get(order.trade_id, tenant=current_user.tenant)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    result = executor.send_order(order.trade_id, order.side, order.quantity, order.price, order.order_type)
    return result

@router.get("/orders")
async def list_orders(current_user: User = Depends(get_current_user)):
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
