from fastapi import APIRouter, Depends, Query
from chronos_v5.pricing_engine import PricingEngine
from chronos_v5.api.dependencies import get_api_key

router = APIRouter()
engine = PricingEngine()

@router.get("/quote", dependencies=[Depends(get_api_key)])
def get_quote(counterparty_id: str, instrument_type: str, notional: float):
    price = engine.get_client_price(counterparty_id, instrument_type, notional)
    return price
