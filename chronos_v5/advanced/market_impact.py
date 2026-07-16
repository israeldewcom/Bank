import redis
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.advanced.advanced_config import AdvancedConfig

class MarketImpactEstimator:
    def __init__(self):
        self.redis = redis.from_url(Config.REDIS_URL)
        self.default_adv = {
            "TBILL": 5e9,
            "BOND": 2e9,
            "EQUITY": 1e9,
            "CASH": 10e9
        }

    def get_daily_volume(self, asset_type: str) -> float:
        key = f"adv:{asset_type}"
        adv = self.redis.get(key)
        if adv:
            return float(adv)
        return self.default_adv.get(asset_type, 1e9)

    def get_penalty(self, asset_type: str, quantity: float) -> float:
        if not AdvancedConfig.MARKET_IMPACT_ENABLED:
            return 0.0
        adv = self.get_daily_volume(asset_type)
        if adv <= 0:
            return 0.0
        pct = quantity / adv
        if pct <= AdvancedConfig.MARKET_IMPACT_DAILY_VOLUME_PCT:
            return 0.0
        excess = pct - AdvancedConfig.MARKET_IMPACT_DAILY_VOLUME_PCT
        penalty = excess * AdvancedConfig.MARKET_IMPACT_COEFFICIENT
        penalty = min(penalty, 0.05)
        logger.debug(f"Market impact penalty for {asset_type}: {penalty:.4f} (pct={pct:.2%})")
        return penalty
