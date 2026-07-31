from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
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
    # Caller-supplied idempotency key. If the same trade is retried with the same
    # client_order_id, the second call returns the original result instead of
    # placing a duplicate order at the gateway. If omitted, one is generated, but
    # callers that may retry on timeout should always supply their own.
    client_order_id: Optional[str] = Field(default=None, max_length=64)


@router.post("/order")
async def place_order(order: OrderRequest, current_user: User = Depends(get_current_user)):
    repo = TradeRepositoryAsync()
    trade = await repo.get(order.trade_id, tenant=current_user.tenant)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    result = await executor.send_order_async(
        trade_id=order.trade_id,
        tenant=current_user.tenant,
        side=order.side,
        quantity=order.quantity,
        price=order.price,
        order_type=order.order_type,
        client_order_id=order.client_order_id,
    )
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
