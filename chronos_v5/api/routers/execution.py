# chronos_v5/api/routers/execution.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import select
from chronos_v5.settlement_execution import SettlementExecution
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.repositories.trade_repository import TradeRepositoryAsync
from chronos_v5.models import User, ExecutionOrder
from chronos_v5.database import AsyncSessionLocal

router = APIRouter()
executor = SettlementExecution()


class OrderRequest(BaseModel):
    trade_id: str
    side: str
    quantity: float
    price: float
    order_type: str = "LIMIT"
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
async def list_orders(current_user: User = Depends(get_current_user), limit: int = 50):
    async with AsyncSessionLocal() as db:
        stmt = (
            select(ExecutionOrder)
            .where(ExecutionOrder.tenant == current_user.tenant)
            .order_by(ExecutionOrder.sent_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        orders = result.scalars().all()

    return [
        {
            "id": str(o.id),
            "trade_id": o.trade_id,
            "client_order_id": o.client_order_id,
            "side": o.side,
            "quantity": o.quantity,
            "price": o.price,
            "order_type": o.order_type,
            "status": o.status,
            "external_order_id": o.external_order_id,
            "sent_at": o.sent_at.isoformat() if o.sent_at else None,
            "filled_at": o.filled_at.isoformat() if o.filled_at else None,
        }
        for o in orders
    ]
