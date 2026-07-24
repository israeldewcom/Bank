# chronos_v5/risk_engine.py
import numpy as np
from chronos_v5.config import Config
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import RiskMetrics, Trade, MarketDataPoint
from chronos_v5.logger_setup import logger
from datetime import datetime, timedelta

class RiskEngine:
    def __init__(self):
        self.db = SyncSessionLocal()

    def compute_var(self, returns, confidence=0.99):
        return np.percentile(returns, (1-confidence)*100)

    def compute_expected_shortfall(self, returns, confidence=0.99):
        var = self.compute_var(returns, confidence)
        return returns[returns <= var].mean()

    def compute_stress_loss(self, returns, scenario="2008"):
        shocks = {
            "2008": -0.4,
            "COVID": -0.3,
            "NIGERIA_2020": -0.25
        }
        shock = shocks.get(scenario, -0.2)
        return np.mean(returns) * (1 + shock)

    def compute_all(self, desk=None):
        query = self.db.query(Trade).filter(Trade.created_at > datetime.now() - timedelta(days=30))
        if desk:
            query = query.filter(Trade.desk == desk)
        trades = query.all()
        if not trades:
            logger.info("No trades for risk computation")
            return None

        pnl_changes = []
        estimated_count = 0
        total_notional = 0.0

        for t in trades:
            market_data = self.db.query(MarketDataPoint).filter(
                MarketDataPoint.symbol == t.instrument_type,
                MarketDataPoint.timestamp >= t.created_at - timedelta(days=1),
                MarketDataPoint.timestamp <= t.created_at + timedelta(days=1)
            ).order_by(MarketDataPoint.timestamp).all()

            if len(market_data) >= 2:
                start_price = market_data[0].price
                end_price = market_data[-1].price
                change = (end_price - start_price) / start_price if start_price != 0 else 0
                pnl_changes.append(t.notional * change)
                total_notional += t.notional
            else:
                # Exclude trade from risk calculation – log and count
                estimated_count += 1
                logger.debug(f"Trade {t.id} excluded from VaR – no market data for {t.instrument_type}")

        if not pnl_changes:
            logger.warning("No trades with market data; risk metrics cannot be computed.")
            # Return a metrics row indicating data quality issue
            return {
                "desk": desk or "TOTAL",
                "var_99": None,
                "expected_shortfall": None,
                "stress_loss": None,
                "capital_usage": None,
                "data_quality": {
                    "total_trades": len(trades),
                    "estimated_trades": estimated_count,
                    "message": "No trades had market data; VaR not computed"
                }
            }

        returns = np.array(pnl_changes) / total_notional if total_notional > 0 else np.array(pnl_changes)
        var = self.compute_var(returns, Config.VAR_CONFIDENCE)
        es = self.compute_expected_shortfall(returns, Config.VAR_CONFIDENCE)
        stress = self.compute_stress_loss(returns, "NIGERIA_2020")

        metric = RiskMetrics(
            desk=desk or "TOTAL",
            var_99=var,
            expected_shortfall=es,
            stress_loss=stress,
            capital_usage=abs(var) * Config.CAPITAL_REQUIREMENT_SA_CCR
        )
        self.db.add(metric)
        self.db.commit()
        logger.info(f"Risk metrics computed for {desk or 'TOTAL'} (excluded {estimated_count} trades with no market data)")

        # Attach data quality info to the returned object if needed
        # We'll return a dict with metrics plus quality flag
        result = {
            "desk": metric.desk,
            "var_99": metric.var_99,
            "expected_shortfall": metric.expected_shortfall,
            "stress_loss": metric.stress_loss,
            "capital_usage": metric.capital_usage,
            "timestamp": metric.timestamp,
            "data_quality": {
                "total_trades": len(trades),
                "estimated_trades": estimated_count,
                "message": f"Excluded {estimated_count} trades with no market data"
            }
        }
        return result
