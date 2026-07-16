# Advanced module for Chronos v5.2 – profitability & market competition upgrades
import os
from chronos_v5.config import Config

class AdvancedConfig:
    ADVANCED_FEATURES_ENABLED = os.getenv("ADVANCED_FEATURES_ENABLED", "false").lower() == "true"
    STALE_PRICE_WIDENING_ENABLED = os.getenv("STALE_PRICE_WIDENING_ENABLED", "true").lower() == "true"
    STALE_PRICE_MAX_AGE_SEC = int(os.getenv("STALE_PRICE_MAX_AGE_SEC", "5"))
    STALE_PRICE_WIDEN_FACTOR = float(os.getenv("STALE_PRICE_WIDEN_FACTOR", "0.001"))
    LP_OPTIMIZER_ENABLED = os.getenv("LP_OPTIMIZER_ENABLED", "true").lower() == "true"
    LP_OPTIMIZER_INTERVAL_SEC = int(os.getenv("LP_OPTIMIZER_INTERVAL_SEC", "60"))
    LP_MAX_ITERATIONS = int(os.getenv("LP_MAX_ITERATIONS", "1000"))
    CBN_EVENT_LISTENER_ENABLED = os.getenv("CBN_EVENT_LISTENER_ENABLED", "true").lower() == "true"
    CBN_EVENT_POLL_INTERVAL_SEC = int(os.getenv("CBN_EVENT_POLL_INTERVAL_SEC", "10"))
    CBN_RSS_FEED_URL = os.getenv("CBN_RSS_FEED_URL", "https://www.cbn.gov.ng/rss/feed.xml")
    SHADOW_VAR_ENABLED = os.getenv("SHADOW_VAR_ENABLED", "true").lower() == "true"
    SHADOW_VAR_LOOKBACK_DAYS = int(os.getenv("SHADOW_VAR_LOOKBACK_DAYS", "30"))
    SHADOW_VAR_UPDATE_INTERVAL_SEC = int(os.getenv("SHADOW_VAR_UPDATE_INTERVAL_SEC", "300"))
    ADVANCED_ALPHA_ENABLED = os.getenv("ADVANCED_ALPHA_ENABLED", "true").lower() == "true"
    ADVANCED_ALPHA_MODEL_PATH = os.getenv("ADVANCED_ALPHA_MODEL_PATH", "./advanced_alpha_model.pkl")
    PERFORMANCE_FEE_OPTIMIZATION_ENABLED = os.getenv("PERFORMANCE_FEE_OPTIMIZATION_ENABLED", "true").lower() == "true"
    DYNAMIC_CALIBRATION_ENABLED = os.getenv("DYNAMIC_CALIBRATION_ENABLED", "true").lower() == "true"
    CALIBRATION_INTERVAL_SEC = int(os.getenv("CALIBRATION_INTERVAL_SEC", "60"))
    CALIBRATION_OMO_BASE = float(os.getenv("CALIBRATION_OMO_BASE", "0.18"))
    MARKET_IMPACT_ENABLED = os.getenv("MARKET_IMPACT_ENABLED", "true").lower() == "true"
    MARKET_IMPACT_DAILY_VOLUME_PCT = float(os.getenv("MARKET_IMPACT_DAILY_VOLUME_PCT", "0.05"))
    MARKET_IMPACT_COEFFICIENT = float(os.getenv("MARKET_IMPACT_COEFFICIENT", "0.1"))
    BACKFILL_TRAINING_ENABLED = os.getenv("BACKFILL_TRAINING_ENABLED", "false").lower() == "true"
    BACKFILL_CSV_PATH = os.getenv("BACKFILL_CSV_PATH", "./historical_settlements.csv")
    BACKFILL_MODEL_OUTPUT = os.getenv("BACKFILL_MODEL_OUTPUT", Config.MODEL_PATH)
