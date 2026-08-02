# chronos_v5/api/routers/nibss.py
# No mock data. No global singleton. Settlements list is derived from real
# Trade rows for the caller's tenant — there is no separate settlements
# table yet, so this reflects trades this tenant has actually submitted,
# not a live NIBSS reconciliation feed.
#
# SECURITY FIX: tenant is now taken exclusively from current_user.tenant.
# This file previously used get_tenant_from_request (header-derived), which
# meant any authenticated user could settle trades, recall collateral, or
# read settlement history under a tenant they don't belong to just by
# setting X-Tenant. That import is gone; every handler below uses the
# authenticated user's own tenant.
#
# RELIABILITY FIX: settle() previously re-wrote trade.status/nibss_ref/
# settled_at itself after calling submit_settlement(), duplicating (and now
# conflicting with) the status management NIBSSClient does internally via
# _reserve_settlement()/_finalize_settlement(). That duplicate write didn't
# know about the SETTLING / SETTLEMENT_FAILED / DUPLICATE states the client
# now uses for idempotent retries, so e.g. a DUPLICATE result (meaning this
# call made no network request at all) would still get stamped SETTLED here.
# NIBSSClient is now the single owner of trade.status/nibss_ref/settled_at
# for the settlement lifecycle; this handler only reads the result back.
from fastapi import APIRouter, Depends
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel
from typing import Optional
from chronos_v5.nibss_client import NIBSSClient
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.models import User, Trade
from chronos_v5.database import SyncSessionLocal
from fastapi import Request

router = APIRouter()

class SettlementRequest(BaseModel):
    trade_id: str
    amount: float
    counterparty_bvn: str
    collateral_ref: Optional[str] = None

@router.post("/settle", dependencies=[Depends(RateLimiter(times=20, seconds=60))])
def settle(req: SettlementRequest, request: Request, current_user: User = Depends(get_current_user)):
    tenant = current_user.tenant
    db = SyncSessionLocal()
    try:
        trade = db.query(Trade).filter(Trade.id == req.trade_id, Trade.tenant == tenant).first()
        if not trade:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Trade not found")
    finally:
        db.close()

    client = NIBSSClient(tenant=tenant)
    return client.submit_settlement(req.trade_id, req.amount, req.counterparty_bvn, req.collateral_ref)

@router.post("/recall", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
def recall(ref: str, request: Request, current_user: User = Depends(get_current_user)):
    tenant = current_user.tenant
    client = NIBSSClient(tenant=tenant)
    return client.recall_collateral(ref)

@router.get("/settlements")
def get_settlements(request: Request, current_user: User = Depends(get_current_user), limit: int = 50):
    tenant = current_user.tenant
    db = SyncSessionLocal()
    try:
        trades = (
            db.query(Trade)
            .filter(Trade.tenant == tenant, Trade.status == "SETTLED")
            .order_by(Trade.settled_at.desc())
            .limit(limit)
            .all()
        )
        total_volume = sum(t.notional for t in trades)
        return {
            "settlements": [
                {
                    "trade_id": t.id,
                    "ref": t.nibss_ref,
                    "amount": t.notional,
                    "currency": t.currency,
                    "status": t.status,
                    "settled_at": t.settled_at.isoformat() if t.settled_at else None,
                }
                for t in trades
            ],
            "total_volume": total_volume,
            "count": len(trades),
        }
    finally:
        db.close()
