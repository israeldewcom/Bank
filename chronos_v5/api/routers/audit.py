from fastapi import APIRouter, Depends, HTTPException
from chronos_v5.repositories.audit_repository import AuditRepository
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.models import User
from datetime import datetime, timezone

router = APIRouter()
repo = AuditRepository()

@router.get("/trade/{trade_id}")
def audit_trade(trade_id: str, current_user: User = Depends(get_current_user)):
    result = repo.get_trade_audit(trade_id, tenant=current_user.tenant)
    if not result.get("trade"):
        raise HTTPException(status_code=404, detail="Trade not found")
    return result

@router.get("/logs")
async def get_audit_logs(current_user: User = Depends(get_current_user)):
    # STUB: not backed by a real audit log table/tenant filter yet.
    # Do not rely on this endpoint for compliance/regulatory audit trails.
    return [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "admin@chronos.com",
            "action": "Login",
            "resource": "System",
            "status": "SUCCESS"
        },
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "admin@chronos.com",
            "action": "Trade Execute",
            "resource": "EUR/USD",
            "status": "SUCCESS"
        }
    ]
