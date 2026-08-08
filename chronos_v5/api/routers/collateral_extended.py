# chronos_v5/api/routers/collateral_extended.py
from fastapi import APIRouter, Depends, HTTPException, Query
from chronos_v5.api.dependencies import get_current_user, get_admin_user
from chronos_v5.models import User, MarginCall, Portfolio, RehypothecationData, CollateralHolding
from chronos_v5.database import SyncSessionLocal
from chronos_v5.logger_setup import logger
from datetime import datetime, timezone
import uuid
from sqlalchemy import func

router = APIRouter(prefix="/collateral", tags=["Collateral Extended"])

# ========== MARGIN CALLS ==========
@router.get("/margin-calls")
def get_margin_calls(
    status: str = Query(None, regex="^(pending|urgent|scheduled|resolved)$"),
    current_user: User = Depends(get_current_user)
):
    db = SyncSessionLocal()
    try:
        query = db.query(MarginCall).filter(MarginCall.tenant == current_user.tenant)
        if status:
            query = query.filter(MarginCall.status == status)
        calls = query.order_by(MarginCall.due_date).all()
        return [
            {
                "id": c.id,
                "counterparty": c.counterparty_id,
                "amount": c.amount,
                "due_date": c.due_date.isoformat(),
                "status": c.status,
                "created_at": c.created_at.isoformat(),
            }
            for c in calls
        ]
    finally:
        db.close()

@router.post("/margin-calls/{call_id}/resolve")
def resolve_margin_call(call_id: str, current_user: User = Depends(get_current_user)):
    db = SyncSessionLocal()
    try:
        call = db.query(MarginCall).filter(
            MarginCall.id == call_id,
            MarginCall.tenant == current_user.tenant
        ).first()
        if not call:
            raise HTTPException(404, "Margin call not found")
        call.status = 'resolved'
        call.resolved_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "resolved", "id": call_id}
    finally:
        db.close()

# ========== PORTFOLIO ==========
@router.get("/portfolio")
def get_portfolio(current_user: User = Depends(get_current_user)):
    db = SyncSessionLocal()
    try:
        portfolio = db.query(Portfolio).filter(Portfolio.tenant == current_user.tenant).first()
        if not portfolio:
            portfolio = Portfolio(
                id=str(uuid.uuid4()),
                tenant=current_user.tenant,
                total_value=0.0,
                cash_balance=0.0
            )
            db.add(portfolio)
            db.commit()
            db.refresh(portfolio)
        return {
            "id": portfolio.id,
            "total_value": portfolio.total_value,
            "cash_balance": portfolio.cash_balance,
            "last_updated": portfolio.last_updated.isoformat(),
        }
    finally:
        db.close()

# ========== REHYPOTHECATION ==========
@router.get("/rehypothecation")
def get_rehypothecation(current_user: User = Depends(get_current_user)):
    db = SyncSessionLocal()
    try:
        data = db.query(RehypothecationData).filter(
            RehypothecationData.tenant == current_user.tenant
        ).all()
        total_rehypo = sum(d.rehypothecated_amount for d in data)
        total_collateral = db.query(CollateralHolding).filter(
            CollateralHolding.tenant == current_user.tenant
        ).with_entities(func.sum(CollateralHolding.market_value)).scalar() or 0.0
        ratio = total_rehypo / total_collateral if total_collateral > 0 else 0.0
        return {
            "rehypothecation_ratio": ratio,
            "total_rehypothecated": total_rehypo,
            "available_collateral": total_collateral - total_rehypo,
            "details": [
                {
                    "collateral_id": d.collateral_id,
                    "amount": d.rehypothecated_amount,
                    "ratio": d.ratio,
                }
                for d in data
            ]
        }
    finally:
        db.close()
