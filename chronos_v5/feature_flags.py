import os
import redis
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

class FeatureFlags:
    """
    Centralized feature toggle system.
    Flags can be set via environment variables or overridden per tenant via Redis.
    """
    def __init__(self):
        self.redis = redis.from_url(Config.REDIS_URL)
        self._cache = {}

    def _get_flag(self, flag_name: str, default: bool = False) -> bool:
        # First check environment
        env_val = os.getenv(f"FEATURE_{flag_name.upper()}")
        if env_val is not None:
            return env_val.lower() == "true"
        # Then check Redis (per-tenant override)
        key = f"feature:{flag_name}"
        val = self.redis.get(key)
        if val is not None:
            return val.decode().lower() == "true"
        return default

    def is_enabled(self, flag_name: str) -> bool:
        if flag_name not in self._cache:
            self._cache[flag_name] = self._get_flag(flag_name)
        return self._cache[flag_name]

    def set_flag(self, flag_name: str, enabled: bool, tenant: str = None):
        key = f"feature:{flag_name}"
        if tenant:
            key = f"tenant:{tenant}:{key}"
        self.redis.setex(key, 3600, "true" if enabled else "false")
        self._cache[flag_name] = enabled

    def invalidate_cache(self):
        self._cache.clear()

# Global instance
feature_flags = FeatureFlags()
