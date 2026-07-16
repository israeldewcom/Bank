from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from chronos_v5.database import AsyncSessionLocal, async_database
from chronos_v5.repositories.trade_repository import TradeRepositoryAsync
from chronos_v5.services.predictor import SettlementPredictor
from chronos_v5.pricing_engine import PricingEngine
from chronos_v5.api.dependencies import get_api_key
from chronos_v5.tasks import attribute_pnl, generate_alpha_signals
from chronos_v5.config import Config
import asyncio

router = APIRouter()

class TradeIngest(BaseModel):
    id: str = Field(..., max_length=36)
    desk: str = Field(..., max_length=100)
    counterparty_id: str = Field(..., max_length=100)
    instrument_type: Optional[str] = None
    currency: str = Field(..., max_length=10)
    notional: float = Field(..., gt=0)
    settle_date: str
    idempotency_key: Optional[str] = None

    @validator('settle_date')
    def validate_settle_date(cls, v):
        try:
            dt = datetime.fromisoformat(v)
            if dt < datetime.now(timezone.utc):
                raise ValueError("Settle date must be in future")
            return v
        except ValueError as e:
            raise ValueError(f"Invalid settle_date: {e}")

class TradeResponse(BaseModel):
    status: str
    trade_id: str
    fail_probability: float
    recommended_action: str
    price: Optional[dict] = None

@router.post("/ingest", dependencies=[Depends(get_api_key), Depends(RateLimiter(times=500, seconds=60))])
async def ingest_trade_async(trade: TradeIngest,
                             background_tasks: BackgroundTasks):
    if not Config.ASYNC_DB or async_database is None:
        raise HTTPException(status_code=501, detail="Async DB not enabled")
    repo = TradeRepositoryAsync()
    existing = await repo.get_by_idempotency(trade.idempotency_key)
    if existing:
        return {"status": "DUPLICATE", "trade": existing}
    trade_id = await repo.insert(trade.dict(), trade.idempotency_key)
    predictor = SettlementPredictor()
    prob = await predictor.predict_async(trade.dict())
    await predictor.predict_and_store_async(trade.dict())
    pricing = PricingEngine()
    price = await pricing.get_client_price_async(trade.counterparty_id, trade.instrument_type or 'UNKNOWN', trade.notional)
    background_tasks.add_task(generate_alpha_signals.delay)
    if prob > 0.15:
        avoided_cost = trade.notional * Config.EMERGENCY_BORROW_RATE
        background_tasks.add_task(attribute_pnl.delay, trade_id, "AVOIDED_FAIL", avoided_cost * 0.5)
    return TradeResponse(
        status="INGESTED",
        trade_id=trade_id,
        fail_probability=prob,
        recommended_action="AUTO_BORROW" if prob > 0.15 else "STANDARD",
        price=price
    )

@router.post("/ingest_sync", dependencies=[Depends(get_api_key), Depends(RateLimiter(times=500, seconds=60))])
def ingest_trade_sync(trade: TradeIngest, background_tasks: BackgroundTasks):
    from chronos_v5.repositories.trade_repository import TradeRepository
    repo = TradeRepository()
    existing = repo.get_by_idempotency(trade.idempotency_key)
    if existing:
        return {"status": "DUPLICATE", "trade": existing}
    trade_id = repo.insert(trade.dict(), trade.idempotency_key)
    predictor = SettlementPredictor()
    prob = predictor.predict(trade.dict())
    pricing = PricingEngine()
    price = pricing.get_client_price(trade.counterparty_id, trade.instrument_type or 'UNKNOWN', trade.notional)
    background_tasks.add_task(generate_alpha_signals.delay)
    if prob > 0.15:
        avoided_cost = trade.notional * Config.EMERGENCY_BORROW_RATE
        background_tasks.add_task(attribute_pnl.delay, trade_id, "AVOIDED_FAIL", avoided_cost * 0.5)
    return TradeResponse(
        status="INGESTED",
        trade_id=trade_id,
        fail_probability=prob,
        recommended_action="AUTO_BORROW" if prob > 0.15 else "STANDARD",
        price=price
    )

@router.get("/{trade_id}")
async def get_trade(trade_id: str):
    repo = TradeRepositoryAsync()
    trade = await repo.get(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade

@router.get("/")
async def list_trades(limit: int = 50, offset: int = 0):
    repo = TradeRepositoryAsync()
    trades = await repo.get_all(limit=limit, offset=offset)
    return trades
