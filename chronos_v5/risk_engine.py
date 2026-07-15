import numpy as np
import pandas as pd
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
        # Fetch actual historical returns from trades and market data
        query = self.db.query(Trade).filter(Trade.created_at > datetime.now() - timedelta(days=30))
        if desk:
            query = query.filter(Trade.desk == desk)
        trades = query.all()
        if not trades:
            logger.info("No trades for risk computation")
            return None

        # Compute actual daily PnL changes using market data
        pnl_changes = []
        for t in trades:
            # Get market prices around trade date
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
            else:
                # Fallback to historical volatility if no market data
                # Use average volatility from market data table
                vol = self._get_historical_volatility(t.instrument_type)
                change = np.random.normal(0, vol)  # Simulate with historical vol
                pnl_changes.append(t.notional * change)

        if not pnl_changes:
            return None

        returns = np.array(pnl_changes) / sum(t.notional for t in trades)
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
        logger.info(f"Risk metrics computed for {desk or 'TOTAL'}")
        return metric

    def _get_historical_volatility(self, instrument_type):
        # Get average daily return volatility from market_data for last 30 days
        cutoff = datetime.now() - timedelta(days=30)
        data = self.db.query(MarketDataPoint).filter(
            MarketDataPoint.symbol == instrument_type,
            MarketDataPoint.timestamp > cutoff
        ).order_by(MarketDataPoint.timestamp).all()
        if len(data) > 1:
            prices = [d.price for d in data]
            returns = np.diff(prices) / prices[:-1]
            return np.std(returns) if len(returns) > 0 else 0.02
        return 0.02  # default
