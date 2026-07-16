import numpy as np
from scipy.optimize import linprog
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import CollateralHolding, AlphaSignal
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.advanced.advanced_config import AdvancedConfig
from chronos_v5.advanced.dynamic_calibrator import DynamicCalibrator
from chronos_v5.advanced.market_impact import MarketImpactEstimator
from datetime import datetime, timedelta

class AdvancedProfitOptimizer:
    def __init__(self):
        self.db = SyncSessionLocal()
        self.alpha_signals = {}
        self.counterparty_limits = {}
        self.calibrator = DynamicCalibrator() if AdvancedConfig.DYNAMIC_CALIBRATION_ENABLED else None
        self.impact_estimator = MarketImpactEstimator() if AdvancedConfig.MARKET_IMPACT_ENABLED else None

    def load_data(self):
        signals = self.db.query(AlphaSignal).filter(
            AlphaSignal.generated_at > datetime.now() - timedelta(minutes=10)
        ).all()
        for s in signals:
            self.alpha_signals[s.asset] = s.signal_value
        self.holdings = self.db.query(CollateralHolding).filter(
            CollateralHolding.eligible == True
        ).all()
        self.counterparty_limits = {h.counterparty_id: 1e9 for h in self.holdings}

    def optimize(self):
        if not AdvancedConfig.LP_OPTIMIZER_ENABLED:
            logger.info("LP optimizer disabled, using simple optimizer")
            return self._simple_optimize()
        self.load_data()
        if not self.holdings:
            logger.info("No collateral holdings to optimize")
            return
        if self.calibrator:
            base_yield = self.calibrator.get_current_yield()
        else:
            base_yield = Config.REHYPOTHECATION_YIELD
        n = len(self.holdings)
        c = []
        for h in self.holdings:
            alpha = self.alpha_signals.get(h.asset_type, 0.0)
            yield_ = base_yield * (1 + alpha)
            cost = h.haircut
            if self.impact_estimator:
                volume_penalty = self.impact_estimator.get_penalty(h.asset_type, h.quantity)
                cost += volume_penalty
            net_benefit = yield_ - cost
            c.append(-net_benefit)
        A_ub = []
        b_ub = []
        for i, h in enumerate(self.holdings):
            row = [0]*n
            row[i] = 1
            A_ub.append(row)
            b_ub.append(h.quantity)
        counterparty_indices = {}
        for i, h in enumerate(self.holdings):
            cid = h.counterparty_id
            counterparty_indices.setdefault(cid, []).append(i)
        for cid, indices in counterparty_indices.items():
            row = [0]*n
            for idx in indices:
                row[idx] = 1
            A_ub.append(row)
            b_ub.append(self.counterparty_limits.get(cid, 1e9))
        risk_budget = sum(h.market_value for h in self.holdings) * 0.1
        row_risk = [h.haircut for h in self.holdings]
        A_ub.append(row_risk)
        b_ub.append(risk_budget)
        bounds = [(0, None)] * n
        try:
            res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
            if res.success:
                allocations = res.x
                for i, h in enumerate(self.holdings):
                    new_quantity = max(0, allocations[i])
                    h.quantity = new_quantity
                self.db.commit()
                logger.info(f"LP optimizer applied allocations, total benefit: {-res.fun:.2f}")
                return res
            else:
                logger.warning(f"LP optimization failed: {res.message}, falling back to simple")
                return self._simple_optimize()
        except Exception as e:
            logger.error(f"LP optimizer error: {e}, falling back to simple")
            return self._simple_optimize()

    def _simple_optimize(self):
        from chronos_v5.profit_optimizer import ProfitOptimizer
        simple = ProfitOptimizer()
        simple.db = self.db
        simple.alpha_signals = self.alpha_signals
        return simple.optimize_rehypothecation()

    def run(self):
        return self.optimize()
