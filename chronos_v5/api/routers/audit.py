from fastapi import APIRouter, Depends
from chronos_v5.repositories.audit_repository import AuditRepository
from chronos_v5.api.dependencies import get_api_key
from datetime import datetime, timezone

router = APIRouter()
repo = AuditRepository()

@router.get("/trade/{trade_id}", dependencies=[Depends(get_api_key)])
def audit_trade(trade_id: str):
    return repo.get_trade_audit(trade_id)

@router.get("/logs", dependencies=[Depends(get_api_key)])
async def get_audit_logs():
    # Return mock audit logs – replace with real data when available
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
