# chronos_v5/repositories/trade_repository.py
from chronos_v5.database import SyncSessionLocal, async_database, AsyncSessionLocal
from chronos_v5.models import Trade
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime, timezone
from chronos_v5.logger_setup import logger

def _to_naive_utc(dt: datetime) -> datetime:
    """Ensure datetime is offset-naive UTC (no timezone info)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

class TradeRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def insert(self, trade_data: dict, idempotency_key: str = None) -> str:
        try:
            settle_dt = datetime.fromisoformat(trade_data['settle_date'])
            settle_dt = _to_naive_utc(settle_dt)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            trade = Trade(
                id=trade_data.get('id', str(uuid.uuid4())),
                desk=trade_data['desk'],
                counterparty_id=trade_data['counterparty_id'],
                instrument_type=trade_data.get('instrument_type'),
                currency=trade_data['currency'],
                notional=trade_data['notional'],
                settle_date=settle_dt,
                created_at=now,
                idempotency_key=idempotency_key
            )
            self.db.add(trade)
            self.db.commit()
            return trade.id
        except Exception as e:
            self.db.rollback()
            logger.error(f"Trade insert failed: {e}")
            raise

    def get(self, trade_id: str):
        try:
            return self.db.query(Trade).filter(Trade.id == trade_id).first()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Trade get failed: {e}")
            raise

    def get_by_idempotency(self, key: str):
        if not key:
            return None
        try:
            return self.db.query(Trade).filter(Trade.idempotency_key == key).first()
        except Exception as e:
            self.db.rollback()
            logger.error(f"get_by_idempotency failed: {e}")
            raise

    def get_all(self, limit=50, offset=0):
        try:
            return self.db.query(Trade).order_by(desc(Trade.created_at)).limit(limit).offset(offset).all()
        except Exception as e:
            self.db.rollback()
            logger.error(f"get_all failed: {e}")
            raise

class TradeRepositoryAsync:
    async def insert(self, trade_data: dict, idempotency_key: str = None) -> str:
        async with AsyncSessionLocal() as session:
            try:
                settle_dt = datetime.fromisoformat(trade_data['settle_date'])
                settle_dt = _to_naive_utc(settle_dt)
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                trade = Trade(
                    id=trade_data.get('id', str(uuid.uuid4())),
                    desk=trade_data['desk'],
                    counterparty_id=trade_data['counterparty_id'],
                    instrument_type=trade_data.get('instrument_type'),
                    currency=trade_data['currency'],
                    notional=trade_data['notional'],
                    settle_date=settle_dt,
                    created_at=now,
                    idempotency_key=idempotency_key
                )
                session.add(trade)
                await session.commit()
                return trade.id
            except Exception as e:
                await session.rollback()
                logger.error(f"Async trade insert failed: {e}")
                raise

    async def get(self, trade_id: str):
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(select(Trade).where(Trade.id == trade_id))
                return result.scalar_one_or_none()
            except Exception as e:
                await session.rollback()
                logger.error(f"Async trade get failed: {e}")
                raise

    async def get_by_idempotency(self, key: str):
        if not key:
            return None
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(select(Trade).where(Trade.idempotency_key == key))
                return result.scalar_one_or_none()
            except Exception as e:
                await session.rollback()
                logger.error(f"Async get_by_idempotency failed: {e}")
                raise

    async def get_all(self, limit=50, offset=0):
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(select(Trade).order_by(desc(Trade.created_at)).limit(limit).offset(offset))
                return result.scalars().all()
            except Exception as e:
                await session.rollback()
                logger.error(f"Async get_all failed: {e}")
                raise
