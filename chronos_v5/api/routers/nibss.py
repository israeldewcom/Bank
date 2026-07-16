from fastapi import APIRouter, Depends, HTTPException
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel
from typing import Optional
from chronos_v5.nibss_client import nibss_client
from chronos_v5.api.dependencies import get_api_key

router = APIRouter()

class SettlementRequest(BaseModel):
    trade_id: str
    amount: float
    counterparty_bvn: str
    collateral_ref: Optional[str] = None

@router.post("/settle", dependencies=[Depends(get_api_key), Depends(RateLimiter(times=20, seconds=60))])
def settle(req: SettlementRequest):
    result = nibss_client.submit_settlement(req.trade_id, req.amount, req.counterparty_bvn, req.collateral_ref)
    return result

@router.post("/recall", dependencies=[Depends(get_api_key)])
def recall(ref: str):
    return nibss_client.recall_collateral(ref)
