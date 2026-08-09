# chronos_v5/api/routers/execution.py
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from chronos_v5.settlement_execution import SettlementExecution
from chronos_v5.api.dependencies import get_current_user, get_admin_user
from chronos_v5.repositories.trade_repository import TradeRepositoryAsync
from chronos_v5.models import User, ExecutionOrder
from chronos_v5.database import SyncSessionLocal
from chronos_v5.logger_setup import logger
from sqlalchemy import desc, and_

router = APIRouter()
executor = SettlementExecution()


class OrderRequest(BaseModel):
    trade_id: str
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    order_type: str = Field("LIMIT", pattern="^(LIMIT|MARKET)$")
    client_order_id: Optional[str] = Field(default=None, max_length=64)


class CancelOrderRequest(BaseModel):
    reason: Optional[str] = None


@router.post("/order", dependencies=[Depends(RateLimiter(times=100, seconds=60))])
async def place_order(order: OrderRequest, current_user: User = Depends(get_current_user)):
    """
    Place an execution order for a trade.
    Idempotent via client_order_id.
    """
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
async def list_orders(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, regex="^(PENDING|SENT|FILLED|FAILED|CANCELLED)$"),
    current_user: User = Depends(get_current_user)
):
    """
    List execution orders for the current tenant.
    """
    db = SyncSessionLocal()
    try:
        query = db.query(ExecutionOrder).filter(ExecutionOrder.tenant == current_user.tenant)
        if status:
            query = query.filter(ExecutionOrder.status == status)
        orders = query.order_by(desc(ExecutionOrder.sent_at)).limit(limit).offset(offset).all()
        return [
            {
                "id": o.id,
                "trade_id": o.trade_id,
                "client_order_id": o.client_order_id,
                "side": o.side,
                "quantity": o.quantity,
                "price": o.price,
                "order_type": o.order_type,
                "status": o.status,
                "external_order_id": o.external_order_id,
                "gateway_response": o.gateway_response,
                "sent_at": o.sent_at.isoformat() if o.sent_at else None,
                "filled_at": o.filled_at.isoformat() if o.filled_at else None,
            }
            for o in orders
        ]
    finally:
        db.close()


@router.get("/orders/{order_id}")
async def get_order(order_id: str, current_user: User = Depends(get_current_user)):
    """
    Get a specific execution order.
    """
    db = SyncSessionLocal()
    try:
        order = db.query(ExecutionOrder).filter(
            ExecutionOrder.id == order_id,
            ExecutionOrder.tenant == current_user.tenant
        ).first()
        if not order:
            raise HTTPException(404, "Order not found")
        return {
            "id": order.id,
            "trade_id": order.trade_id,
            "client_order_id": order.client_order_id,
            "side": order.side,
            "quantity": order.quantity,
            "price": order.price,
            "order_type": order.order_type,
            "status": order.status,
            "external_order_id": order.external_order_id,
            "gateway_response": order.gateway_response,
            "sent_at": order.sent_at.isoformat() if order.sent_at else None,
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
        }
    finally:
        db.close()


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    cancel_req: Optional[CancelOrderRequest] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Cancel a pending execution order.
    """
    db = SyncSessionLocal()
    try:
        order = db.query(ExecutionOrder).filter(
            ExecutionOrder.id == order_id,
            ExecutionOrder.tenant == current_user.tenant
        ).first()
        if not order:
            raise HTTPException(404, "Order not found")
        if order.status not in ("PENDING", "SENT"):
            raise HTTPException(400, f"Cannot cancel order with status: {order.status}")

        order.status = "CANCELLED"
        if cancel_req and cancel_req.reason:
            if not order.gateway_response:
                order.gateway_response = {}
            order.gateway_response["cancellation_reason"] = cancel_req.reason
        db.commit()

        logger.info(f"Order {order_id} cancelled for tenant {current_user.tenant}")
        return {"status": "cancelled", "order_id": order_id, "reason": cancel_req.reason if cancel_req else None}
    finally:
        db.close()


@router.get("/analytics")
async def get_execution_analytics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user)
):
    """
    Get execution analytics for the current tenant.
    """
    db = SyncSessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        orders = db.query(ExecutionOrder).filter(
            ExecutionOrder.tenant == current_user.tenant,
            ExecutionOrder.sent_at >= cutoff
        ).all()

        total = len(orders)
        filled = sum(1 for o in orders if o.status == 'FILLED')
        failed = sum(1 for o in orders if o.status == 'FAILED')
        pending = sum(1 for o in orders if o.status in ('PENDING', 'SENT'))
        cancelled = sum(1 for o in orders if o.status == 'CANCELLED')

        fill_times = []
        for o in orders:
            if o.filled_at and o.sent_at:
                fill_times.append((o.filled_at - o.sent_at).total_seconds())
        avg_fill_time = sum(fill_times) / len(fill_times) if fill_times else None

        total_quantity = sum(o.quantity for o in orders if o.status == 'FILLED')
        total_value = sum(o.quantity * o.price for o in orders if o.status == 'FILLED')

        return {
            "total_orders": total,
            "filled": filled,
            "failed": failed,
            "pending": pending,
            "cancelled": cancelled,
            "fill_rate": filled / total if total > 0 else 0,
            "avg_fill_time_seconds": avg_fill_time,
            "total_filled_quantity": total_quantity,
            "total_filled_value": total_value,
            "period_days": days,
            "tenant": current_user.tenant
        }
    finally:
        db.close()


@router.get("/status")
async def get_execution_status(current_user: User = Depends(get_current_user)):
    """
    Get execution engine status.
    """
    status = {
        "enabled": executor.enabled,
        "fix_url": executor.fix_url if executor.enabled else None,
        "sender_comp_id": executor.sender_comp if executor.enabled else None,
        "target_comp_id": executor.target_comp if executor.enabled else None,
        "tenant": current_user.tenant,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return status
