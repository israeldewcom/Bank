import time
import redis
from chronos_v5.config import Config
from chronos_v5.nigeria_adapter import nigeria
from chronos_v5.logger_setup import logger
from chronos_v5.pricing_engine import PricingEngine
from chronos_v5.advanced.advanced_config import AdvancedConfig
from chronos_v5.advanced.dynamic_calibrator import DynamicCalibrator

class DynamicPricingEngine(PricingEngine):
    def __init__(self):
        super().__init__()
        self.redis = redis.from_url(Config.REDIS_URL)
        self.last_price_time = {}
        self.last_price = {}
        self.stale_enabled = AdvancedConfig.STALE_PRICE_WIDENING_ENABLED
        self.calibrator = DynamicCalibrator() if AdvancedConfig.DYNAMIC_CALIBRATION_ENABLED else None

    def get_client_price(self, counterparty_id: str, instrument_type: str, notional: float) -> dict:
        base_price = super().get_client_price(counterparty_id, instrument_type, notional)
        if self.calibrator:
            calibrated_yield = self.calibrator.get_current_yield()
            base_price['calibrated_yield'] = calibrated_yield
            spread_adj = (calibrated_yield - Config.REHYPOTHECATION_YIELD) * 0.5
            base_price['spread'] = max(0.005, base_price['spread'] - spread_adj)
        if self.stale_enabled:
            symbol = self._get_symbol_for_instrument(instrument_type)
            age = self._get_data_age(symbol)
            if age > AdvancedConfig.STALE_PRICE_MAX_AGE_SEC:
                widen_factor = (age - AdvancedConfig.STALE_PRICE_MAX_AGE_SEC) * AdvancedConfig.STALE_PRICE_WIDEN_FACTOR
                base_price['spread'] += widen_factor
                base_price['fee'] *= (1 + widen_factor)
                base_price['net_price'] = base_price['gross_price'] - base_price['fee']
                logger.info(f"Stale price widening applied: age={age}s, factor={widen_factor:.4f}")
        daily_volume = self._get_daily_volume(instrument_type)
        if daily_volume > 0:
            trade_pct = notional / daily_volume
            if trade_pct > AdvancedConfig.MARKET_IMPACT_DAILY_VOLUME_PCT:
                impact_cost = trade_pct * AdvancedConfig.MARKET_IMPACT_COEFFICIENT * base_price['gross_price']
                base_price['fee'] += impact_cost
                base_price['net_price'] = base_price['gross_price'] - base_price['fee']
                logger.info(f"Market impact added: {impact_cost:.2f} for trade {notional:.0f} vs ADV {daily_volume:.0f}")
        return base_price

    def _get_symbol_for_instrument(self, instrument_type: str) -> str:
        mapping = {
            "TBILL": "NGN_TBILL",
            "BOND": "NGN_BOND",
            "EQUITY": "NGX:ALLSHARE",
            "CASH": "NGN"
        }
        return mapping.get(instrument_type, "NGN")

    def _get_data_age(self, symbol: str) -> float:
        ts = self.redis.get(f"price_time:{symbol}")
        if ts:
            return time.time() - float(ts)
        return 9999

    def _get_daily_volume(self, instrument_type: str) -> float:
        key = f"daily_volume:{instrument_type}"
        vol = self.redis.get(key)
        if vol:
            return float(vol)
        defaults = {"TBILL": 5e9, "BOND": 2e9, "EQUITY": 1e9, "CASH": 10e9}
        return defaults.get(instrument_type, 1e9)
