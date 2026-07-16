from fastapi import APIRouter, Depends
from chronos_v5.repositories.audit_repository import AuditRepository
from chronos_v5.api.dependencies import get_api_key

router = APIRouter()
repo = AuditRepository()

@router.get("/trade/{trade_id}", dependencies=[Depends(get_api_key)])
def audit_trade(trade_id: str):
    return repo.get_trade_audit(trade_id)
