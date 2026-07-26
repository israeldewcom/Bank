from fastapi import APIRouter, Depends, Query
from chronos_v5.pricing_engine import PricingEngine
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.models import User

router = APIRouter()
engine = PricingEngine()

@router.get("/quote")
def get_quote(counterparty_id: str, instrument_type: str, notional: float, current_user: User = Depends(get_current_user)):
    price = engine.get_client_price(counterparty_id, instrument_type, notional)
    return price
