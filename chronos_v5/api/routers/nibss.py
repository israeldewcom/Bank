from fastapi import APIRouter, Depends, HTTPException
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
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

@router.get("/settlements")
async def get_settlements():
    # Return a mock list – replace with real data when available
    return {
        "settlements": [
            {
                "ref": "NIBSS-001",
                "bank": "GTBank",
                "amount": 1_000_000,
                "status": "SETTLED",
                "time": datetime.now(timezone.utc).isoformat()
            },
            {
                "ref": "NIBSS-002",
                "bank": "Zenith",
                "amount": 500_000,
                "status": "PROCESSING",
                "time": datetime.now(timezone.utc).isoformat()
            }
        ],
        "total_volume": 1_500_000,
        "success_rate": 0.998,
        "avg_time": 1.4,
        "pending": 1,
        "connected": True
    }
