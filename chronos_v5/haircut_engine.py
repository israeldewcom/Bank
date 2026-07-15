import redis
from chronos_v5.config import Config
from chronos_v5.nigeria_adapter import nigeria
from chronos_v5.logger_setup import logger

class HaircutEngine:
    def __init__(self):
        self.baseline = Config.HAIRCUT_BASELINE
        self.vol_scale = Config.HAIRCUT_VOLATILITY_SCALE
        self.redis = redis.from_url(Config.REDIS_URL)

    def compute_haircut(self, asset_type: str, maturity_days: int = 0) -> float:
        # Check if dynamic baseline from CBN event is available
        dynamic_baseline = self.redis.get("haircut:baseline")
        if dynamic_baseline:
            baseline = float(dynamic_baseline)
        else:
            baseline = self.baseline
        vol = nigeria.get_asset_volatility(asset_type)
        haircut = baseline + self.vol_scale * vol
        if asset_type in ("TBILL", "BOND"):
            haircut += 0.001 * maturity_days / 365.0
        return min(max(haircut, 0.01), 0.50)

    def apply_haircut_to_value(self, market_value: float, asset_type: str, maturity_days: int = 0) -> float:
        haircut = self.compute_haircut(asset_type, maturity_days)
        discounted = market_value * (1 - haircut)
        return discounted
