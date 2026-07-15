from chronos_v5.config import Config
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import CollateralHolding, AlphaSignal
from chronos_v5.logger_setup import logger
from chronos_v5.nigeria_adapter import nigeria
import numpy as np
from datetime import datetime, timedelta

class ProfitOptimizer:
    def __init__(self):
        self.db = SyncSessionLocal()
        self.alpha_signals = {}

    def load_alpha_signals(self):
        signals = self.db.query(AlphaSignal).filter(
            AlphaSignal.generated_at > datetime.now() - timedelta(minutes=10)
        ).all()
        for s in signals:
            self.alpha_signals[s.asset] = s.signal_value

    def optimize_rehypothecation(self):
        holdings = self.db.query(CollateralHolding).filter(CollateralHolding.eligible == True).all()
        if not holdings:
            logger.info("No collateral holdings to optimize")
            return None
        best_asset = None
        best_score = -np.inf
        for h in holdings:
            alpha = self.alpha_signals.get(h.asset_type, 0)
            yield_ = Config.REHYPOTHECATION_YIELD * (1 + alpha)
            risk = h.haircut
            if risk == 0:
                risk = 0.01
            score = yield_ / risk
            if score > best_score:
                best_score = score
                best_asset = h
        if best_asset:
            logger.info(f"Optimal rehypo asset: {best_asset.asset_type} with score {best_score}")
            for h in holdings:
                if h.id == best_asset.id:
                    h.quantity *= 1.1
                else:
                    h.quantity *= 0.95
            self.db.commit()
        return best_asset

    def run(self):
        self.load_alpha_signals()
        self.optimize_rehypothecation()
