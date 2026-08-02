# chronos_v5/tasks.py
from chronos_v5.celery_app import celery_app
from chronos_v5.logger_setup import logger
from chronos_v5.config import Config

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def attribute_pnl(self, trade_id: str, strategy: str, amount_saved: float, tenant: str = "default"):
    from chronos_v5.models import PnLAttribution
    from chronos_v5.database import SyncSessionLocal
    db = SyncSessionLocal()
    try:
        pnl = PnLAttribution(
            trade_id=trade_id,
            strategy=strategy,
            amount_saved=amount_saved,
            currency="NGN",
            metadata_json='{"source": "predictor"}',
            tenant=tenant
        )
        db.add(pnl)
        db.commit()
        if Config.PERFORMANCE_FEE_ENABLED:
            fee = amount_saved * Config.PERFORMANCE_FEE_PERCENT
            logger.info(f"Performance fee accrued: {fee} NGN on trade {trade_id} for tenant {tenant}")
    finally:
        db.close()

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def generate_alpha_signals(self):
    from chronos_v5.market_data import MarketDataAggregator
    from chronos_v5.models import AlphaSignal
    from chronos_v5.database import SyncSessionLocal
    aggregator = MarketDataAggregator()
    signals = aggregator.compute_alpha()
    db = SyncSessionLocal()
    for asset, value in signals.items():
        sig = AlphaSignal(asset=asset, signal_value=value, strategy=Config.ALPHA_STRATEGY_TYPE)
        db.add(sig)
    db.commit()
    db.close()

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def optimize_rehypothecation(self):
    from chronos_v5.profit_optimizer import ProfitOptimizer
    from chronos_v5.models import TenantConfig
    from chronos_v5.database import SyncSessionLocal
    db = SyncSessionLocal()
    try:
        tenants = [row.tenant for row in db.query(TenantConfig.tenant).all()]
    finally:
        db.close()
    if not tenants:
        logger.warning("optimize_rehypothecation: no tenants found; nothing to optimize")
        return
    for tenant in tenants:
        try:
            optimizer = ProfitOptimizer(tenant=tenant)
            optimizer.run()
        except Exception as e:
            logger.error(f"optimize_rehypothecation failed for tenant {tenant}: {e}")

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def compute_risk_metrics(self):
    from chronos_v5.risk_engine import RiskEngine
    from chronos_v5.models import TenantConfig
    from chronos_v5.database import SyncSessionLocal

    engine = RiskEngine()
    db = SyncSessionLocal()
    try:
        tenants = [row.tenant for row in db.query(TenantConfig.tenant).all()]
    finally:
        db.close()

    if not tenants:
        logger.warning("compute_risk_metrics: no tenants found in TenantConfig; nothing to compute")
        return

    for tenant in tenants:
        try:
            engine.compute_all(tenant=tenant)
        except Exception as e:
            logger.error(f"compute_risk_metrics failed for tenant {tenant}: {e}")
