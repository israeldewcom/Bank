# chronos_v5/api/routers/execution.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from chronos_v5.settlement_execution import SettlementExecution
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.repositories.trade_repository import TradeRepositoryAsync
from chronos_v5.models import User, ExecutionOrder
from chronos_v5.database import SyncSessionLocal
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
    db = SyncSessionLocal()
    try:
        orders = db.query(ExecutionOrder).filter(
            ExecutionOrder.tenant == current_user.tenant
        ).order_by(ExecutionOrder.sent_at.desc()).limit(100).all()
        return [
            {
                "id": o.id,
                "trade_id": o.trade_id,
                "side": o.side,
                "quantity": o.quantity,
                "price": o.price,
                "status": o.status,
                "time": o.sent_at.isoformat() if o.sent_at else None
            }
            for o in orders
        ]
    finally:
        db.close()
