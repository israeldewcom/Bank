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
    optimizer = ProfitOptimizer()
    optimizer.run()

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def compute_risk_metrics(self):
    """
    RELIABILITY FIX: previously called engine.compute_all() with no
    arguments. RiskEngine.compute_all() used to accept a falsy/None tenant
    and silently compute VaR/ES/stress loss across every tenant's trades
    merged together, then persist that blended figure mislabeled under
    tenant "default" — a materially wrong risk number for any bank relying
    on it, not just a missing-filter bug. compute_all() now requires tenant
    and raises if it's missing, so this task must (and now does) iterate
    every real tenant from TenantConfig and compute risk metrics once per
    tenant, matching how every other per-tenant read/write path in this
    codebase works.
    """
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
