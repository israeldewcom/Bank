from fastapi import APIRouter, Depends, HTTPException
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel
from chronos_v5.repositories.collateral_repository import CollateralRepository
from chronos_v5.api.dependencies import get_api_key
from chronos_v5.haircut_engine import HaircutEngine

router = APIRouter()
repo = CollateralRepository()
haircut_engine = HaircutEngine()

class CollateralUpdate(BaseModel):
    counterparty_id: str
    asset_type: str
    quantity: float
    market_value: float

@router.post("/add", dependencies=[Depends(get_api_key), Depends(RateLimiter(times=100, seconds=60))])
def add_collateral(collateral: CollateralUpdate):
    from chronos_v5.models import CollateralHolding
    haircut = haircut_engine.compute_haircut(collateral.asset_type)
    holding = CollateralHolding(
        counterparty_id=collateral.counterparty_id,
        asset_type=collateral.asset_type,
        quantity=collateral.quantity,
        market_value=collateral.market_value,
        haircut=haircut
    )
    db = repo.db
    db.add(holding)
    db.commit()
    return {"status": "added", "id": holding.id}

@router.get("/{counterparty_id}")
def get_collateral(counterparty_id: str):
    holdings = repo.get_by_counterparty(counterparty_id)
    return holdings
