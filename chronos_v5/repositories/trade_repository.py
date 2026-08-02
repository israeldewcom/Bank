# chronos_v5/repositories/trade_repository.py
# SECURITY FIX: tenant used to default to None on get / get_by_idempotency /
# get_all across both classes, meaning a caller could accidentally omit it
# and silently get cross-tenant results. tenant is now a required, non-
# optional parameter on every read method in both TradeRepository and
# TradeRepositoryAsync.
#
# SECURITY FIX (insert): insert() built the Trade row from trade_data but
# never set tenant=trade_data['tenant'], even though every caller in
# api/routers/trade.py computes and passes it. Trade.tenant has a Python-side
# default of "default", so this didn't error — it silently filed every trade
# under the "default" tenant regardless of who submitted it. Combined with
# get()/get_all()/get_by_idempotency() being correctly tenant-filtered, this
# meant real tenants saw empty results (risk_engine.compute_all, dashboards,
# etc. would silently return nothing) while every tenant's trades collapsed
# into one shared bucket under "default". insert() now requires tenant to be
# present in trade_data and writes it onto the row explicitly, matching the
# read-side discipline already enforced below.
from chronos_v5.database import SyncSessionLocal, async_database, AsyncSessionLocal
from chronos_v5.models import Trade
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError  # <-- added
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
            tenant = trade_data.get('tenant')
            if not tenant:
                raise ValueError("trade_data['tenant'] is required for insert() — "
                                  "refusing to fall back to the model default, which "
                                  "would silently mix this trade into the 'default' tenant.")
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
                idempotency_key=idempotency_key,
                tenant=tenant
            )
            self.db.add(trade)
            self.db.commit()
            return trade.id
        except IntegrityError as e:
            self.db.rollback()
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.info(f"Duplicate idempotency key: {idempotency_key}")
                raise ValueError("Duplicate idempotency key") from e
            logger.error(f"Trade insert integrity error: {e}")
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Trade insert failed: {e}")
            raise

    def get(self, trade_id: str, tenant: str):
        try:
            q = self.db.query(Trade).filter(Trade.id == trade_id, Trade.tenant == tenant)
            return q.first()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Trade get failed: {e}")
            raise

    def get_by_idempotency(self, key: str, tenant: str):
        if not key:
            return None
        try:
            q = self.db.query(Trade).filter(Trade.idempotency_key == key, Trade.tenant == tenant)
            return q.first()
        except Exception as e:
            self.db.rollback()
            logger.error(f"get_by_idempotency failed: {e}")
            raise

    def get_all(self, tenant: str, limit=50, offset=0):
        try:
            q = self.db.query(Trade).filter(Trade.tenant == tenant)
            return q.order_by(desc(Trade.created_at)).limit(limit).offset(offset).all()
        except Exception as e:
            self.db.rollback()
            logger.error(f"get_all failed: {e}")
            raise

class TradeRepositoryAsync:
    async def insert(self, trade_data: dict, idempotency_key: str = None) -> str:
        tenant = trade_data.get('tenant')
        if not tenant:
            raise ValueError("trade_data['tenant'] is required for insert() — "
                              "refusing to fall back to the model default, which "
                              "would silently mix this trade into the 'default' tenant.")
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
                    idempotency_key=idempotency_key,
                    tenant=tenant
                )
                session.add(trade)
                await session.commit()
                return trade.id
            except IntegrityError as e:
                await session.rollback()
                if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                    logger.info(f"Duplicate idempotency key: {idempotency_key}")
                    raise ValueError("Duplicate idempotency key") from e
                logger.error(f"Async trade insert integrity error: {e}")
                raise
            except Exception as e:
                await session.rollback()
                logger.error(f"Async trade insert failed: {e}")
                raise

    async def get(self, trade_id: str, tenant: str):
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(Trade).where(Trade.id == trade_id, Trade.tenant == tenant)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
            except Exception as e:
                await session.rollback()
                logger.error(f"Async trade get failed: {e}")
                raise

    async def get_by_idempotency(self, key: str, tenant: str):
        if not key:
            return None
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(Trade).where(Trade.idempotency_key == key, Trade.tenant == tenant)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
            except Exception as e:
                await session.rollback()
                logger.error(f"Async get_by_idempotency failed: {e}")
                raise

    async def get_all(self, tenant: str, limit=50, offset=0):
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(Trade).where(Trade.tenant == tenant)
                stmt = stmt.order_by(desc(Trade.created_at)).limit(limit).offset(offset)
                result = await session.execute(stmt)
                return result.scalars().all()
            except Exception as e:
                await session.rollback()
                logger.error(f"Async get_all failed: {e}")
                raise
