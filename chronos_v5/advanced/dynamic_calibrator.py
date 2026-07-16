import redis, requests, time
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.nigeria_adapter import nigeria
from chronos_v5.advanced.advanced_config import AdvancedConfig

class DynamicCalibrator:
    def __init__(self):
        self.redis = redis.from_url(Config.REDIS_URL)
        self.last_calibration = 0
        self.yield_cache = Config.REHYPOTHECATION_YIELD
        self.borrow_cache = Config.EMERGENCY_BORROW_RATE
        self.haircut_cache = Config.HAIRCUT_BASELINE

    def calibrate(self):
        try:
            mpr = nigeria.cbn_mpr
            omo_rate = mpr + 0.02
            interbank = self.redis.get("ng:interbank_rate")
            if interbank:
                interbank = float(interbank)
            else:
                interbank = mpr + 0.01
            base_yield = AdvancedConfig.CALIBRATION_OMO_BASE
            omo_diff = omo_rate - 0.18
            calibrated_yield = base_yield + omo_diff * 0.5
            calibrated_yield = max(0.10, min(0.30, calibrated_yield))
            calibrated_borrow = interbank + 0.05
            calibrated_borrow = max(0.15, min(0.40, calibrated_borrow))
            vol = nigeria.get_asset_volatility("NGX_EQUITY")
            calibrated_haircut = Config.HAIRCUT_BASELINE + vol * 0.5
            calibrated_haircut = max(0.01, min(0.10, calibrated_haircut))
            self.redis.setex("calibrated:yield", 300, calibrated_yield)
            self.redis.setex("calibrated:borrow", 300, calibrated_borrow)
            self.redis.setex("calibrated:haircut", 300, calibrated_haircut)
            self.yield_cache = calibrated_yield
            self.borrow_cache = calibrated_borrow
            self.haircut_cache = calibrated_haircut
            self.last_calibration = time.time()
            logger.info(f"Calibration updated: yield={calibrated_yield:.4f}, borrow={calibrated_borrow:.4f}, haircut={calibrated_haircut:.4f}")
            return True
        except Exception as e:
            logger.error(f"Calibration failed: {e}")
            return False

    def get_current_yield(self):
        if time.time() - self.last_calibration > AdvancedConfig.CALIBRATION_INTERVAL_SEC:
            self.calibrate()
        cached = self.redis.get("calibrated:yield")
        if cached:
            return float(cached)
        return self.yield_cache

    def get_current_borrow_rate(self):
        if time.time() - self.last_calibration > AdvancedConfig.CALIBRATION_INTERVAL_SEC:
            self.calibrate()
        cached = self.redis.get("calibrated:borrow")
        if cached:
            return float(cached)
        return self.borrow_cache

    def get_current_haircut(self):
        if time.time() - self.last_calibration > AdvancedConfig.CALIBRATION_INTERVAL_SEC:
            self.calibrate()
        cached = self.redis.get("calibrated:haircut")
        if cached:
            return float(cached)
        return self.haircut_cache

    def force_calibration(self):
        return self.calibrate()
