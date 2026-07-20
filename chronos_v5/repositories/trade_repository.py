from chronos_v5.database import SyncSessionLocal, async_database, AsyncSessionLocal
from chronos_v5.models import Trade
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime, timezone

class TradeRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def insert(self, trade_data: dict, idempotency_key: str = None) -> str:
        # Parse settle_date and convert to UTC naive
        settle_dt = datetime.fromisoformat(trade_data['settle_date'])
        if settle_dt.tzinfo is None:
            settle_dt = settle_dt.replace(tzinfo=timezone.utc)
        else:
            settle_dt = settle_dt.astimezone(timezone.utc)
        settle_dt = settle_dt.replace(tzinfo=None)  # store as UTC naive

        trade = Trade(
            id=trade_data.get('id', str(uuid.uuid4())),
            desk=trade_data['desk'],
            counterparty_id=trade_data['counterparty_id'],
            instrument_type=trade_data.get('instrument_type'),
            currency=trade_data['currency'],
            notional=trade_data['notional'],
            settle_date=settle_dt,
            idempotency_key=idempotency_key
        )
        self.db.add(trade)
        self.db.commit()
        return trade.id

    def get(self, trade_id: str):
        return self.db.query(Trade).filter(Trade.id == trade_id).first()

    def get_by_idempotency(self, key: str):
        if not key:
            return None
        return self.db.query(Trade).filter(Trade.idempotency_key == key).first()

    def get_all(self, limit=50, offset=0):
        return self.db.query(Trade).order_by(desc(Trade.created_at)).limit(limit).offset(offset).all()

class TradeRepositoryAsync:
    async def insert(self, trade_data: dict, idempotency_key: str = None) -> str:
        # Parse settle_date and convert to UTC naive
        settle_dt = datetime.fromisoformat(trade_data['settle_date'])
        if settle_dt.tzinfo is None:
            settle_dt = settle_dt.replace(tzinfo=timezone.utc)
        else:
            settle_dt = settle_dt.astimezone(timezone.utc)
        settle_dt = settle_dt.replace(tzinfo=None)

        async with AsyncSessionLocal() as session:
            trade = Trade(
                id=trade_data.get('id', str(uuid.uuid4())),
                desk=trade_data['desk'],
                counterparty_id=trade_data['counterparty_id'],
                instrument_type=trade_data.get('instrument_type'),
                currency=trade_data['currency'],
                notional=trade_data['notional'],
                settle_date=settle_dt,
                idempotency_key=idempotency_key
            )
            session.add(trade)
            await session.commit()
            return trade.id

    async def get(self, trade_id: str):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Trade).where(Trade.id == trade_id))
            return result.scalar_one_or_none()

    async def get_by_idempotency(self, key: str):
        if not key:
            return None
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Trade).where(Trade.idempotency_key == key))
            return result.scalar_one_or_none()

    async def get_all(self, limit=50, offset=0):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Trade).order_by(desc(Trade.created_at)).limit(limit).offset(offset))
            return result.scalars().all()
