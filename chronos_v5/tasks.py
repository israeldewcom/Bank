from chronos_v5.celery_app import celery_app
from chronos_v5.logger_setup import logger
from chronos_v5.config import Config
from chronos_v5.profit_optimizer import ProfitOptimizer
from chronos_v5.risk_engine import RiskEngine

@celery_app.task(bind=True)
def attribute_pnl(self, trade_id: str, strategy: str, amount_saved: float):
    from chronos_v5.models import PnLAttribution
    from chronos_v5.database import SyncSessionLocal
    db = SyncSessionLocal()
    try:
        pnl = PnLAttribution(
            trade_id=trade_id,
            strategy=strategy,
            amount_saved=amount_saved,
            currency="NGN",
            metadata_json='{"source": "predictor"}'
        )
        db.add(pnl)
        db.commit()
        if Config.PERFORMANCE_FEE_ENABLED:
            fee = amount_saved * Config.PERFORMANCE_FEE_PERCENT
            logger.info(f"Performance fee accrued: {fee} NGN on trade {trade_id}")
    finally:
        db.close()

@celery_app.task
def generate_alpha_signals():
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

@celery_app.task
def optimize_rehypothecation():
    from chronos_v5.profit_optimizer import ProfitOptimizer
    optimizer = ProfitOptimizer()
    optimizer.run()

@celery_app.task
def compute_risk_metrics():
    from chronos_v5.risk_engine import RiskEngine
    engine = RiskEngine()
    engine.compute_all()
