# chronos_v5/api/routers/audit.py – updated
from fastapi import APIRouter, Depends, HTTPException
from chronos_v5.repositories.audit_repository import AuditRepository
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.models import User
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Trade, PnLAttribution
from sqlalchemy import desc

router = APIRouter()

@router.get("/logs")
def get_audit_logs(
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    db = SyncSessionLocal()
    try:
        trades = db.query(Trade).filter(
            Trade.tenant == current_user.tenant
        ).order_by(desc(Trade.created_at)).limit(limit).all()
        pnls = db.query(PnLAttribution).filter(
            PnLAttribution.tenant == current_user.tenant
        ).order_by(desc(PnLAttribution.timestamp)).limit(limit).all()
        logs = []
        for t in trades:
            logs.append({
                "timestamp": t.created_at.isoformat() if t.created_at else None,
                "action": "Trade",
                "description": f"Trade {t.id} ingested, status {t.status}",
                "user": "system",
                "details": {"trade_id": t.id, "amount": t.notional}
            })
        for p in pnls:
            logs.append({
                "timestamp": p.timestamp.isoformat() if p.timestamp else None,
                "action": "P&L",
                "description": f"P&L attribution: {p.amount_saved} {p.currency}",
                "user": "system",
                "details": {"trade_id": p.trade_id, "strategy": p.strategy}
            })
        logs.sort(key=lambda x: x['timestamp'], reverse=True)
        return logs[:limit]
    finally:
        db.close()

@router.get("/trade/{trade_id}")
def audit_trade(trade_id: str, current_user: User = Depends(get_current_user)):
    repo = AuditRepository()
    result = repo.get_trade_audit(trade_id, tenant=current_user.tenant)
    if not result.get("trade"):
        raise HTTPException(status_code=404, detail="Trade not found")
    return result
