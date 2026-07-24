# chronos_v5/services/tenant_config_service.py
import redis
import json
from chronos_v5.config import Config
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import TenantConfig
from chronos_v5.logger_setup import logger
from chronos_v5.encryption import encryption

class TenantConfigService:
    def __init__(self):
        self.redis = redis.from_url(Config.REDIS_URL)
        self.cache_ttl = 300

    def get_config(self, tenant: str) -> dict:
        cache_key = f"tenant_config:{tenant}"
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        # Fetch from DB
        db = SyncSessionLocal()
        config = db.query(TenantConfig).filter(TenantConfig.tenant == tenant).first()
        db.close()
        if not config:
            # Return defaults from global Config
            defaults = {
                "tenant": tenant,
                "performance_fee_percent": Config.PERFORMANCE_FEE_PERCENT,
                "bloomberg_api_key": Config.BLOOMBERG_API_KEY,
                "reuters_api_key": Config.REUTERS_API_KEY,
                "alpha_vantage_key": Config.ALPHA_VANTAGE_API_KEY,
                "nibss_api_key": Config.NIBSS_API_KEY,
                "cbn_openapi_url": Config.CBN_OPENAPI_URL,
                "ngx_api_url": Config.NGX_API_URL,
                "use_global_model": True,
                "alpha_strategy_type": Config.ALPHA_STRATEGY_TYPE
            }
            self.redis.setex(cache_key, self.cache_ttl, json.dumps(defaults))
            return defaults
        # Decrypt sensitive fields
        result = {
            "tenant": config.tenant,
            "performance_fee_percent": config.performance_fee_percent,
            "bloomberg_api_key": encryption.decrypt(config.bloomberg_api_key_enc) if config.bloomberg_api_key_enc else None,
            "reuters_api_key": encryption.decrypt(config.reuters_api_key_enc) if config.reuters_api_key_enc else None,
            "alpha_vantage_key": encryption.decrypt(config.alpha_vantage_key_enc) if config.alpha_vantage_key_enc else None,
            "nibss_api_key": encryption.decrypt(config.nibss_api_key_enc) if config.nibss_api_key_enc else None,
            "cbn_openapi_url": config.cbn_openapi_url or Config.CBN_OPENAPI_URL,
            "ngx_api_url": config.ngx_api_url or Config.NGX_API_URL,
            "use_global_model": config.use_global_model,
            "alpha_strategy_type": config.alpha_strategy_type or Config.ALPHA_STRATEGY_TYPE
        }
        self.redis.setex(cache_key, self.cache_ttl, json.dumps(result))
        return result

    def update_config(self, tenant: str, updates: dict):
        db = SyncSessionLocal()
        config = db.query(TenantConfig).filter(TenantConfig.tenant == tenant).first()
        if not config:
            config = TenantConfig(tenant=tenant)
            db.add(config)
        # Update fields – encrypt sensitive ones
        if "performance_fee_percent" in updates:
            config.performance_fee_percent = updates["performance_fee_percent"]
        if "bloomberg_api_key" in updates:
            config.bloomberg_api_key_enc = encryption.encrypt(updates["bloomberg_api_key"]) if updates["bloomberg_api_key"] else None
        if "reuters_api_key" in updates:
            config.reuters_api_key_enc = encryption.encrypt(updates["reuters_api_key"]) if updates["reuters_api_key"] else None
        if "alpha_vantage_key" in updates:
            config.alpha_vantage_key_enc = encryption.encrypt(updates["alpha_vantage_key"]) if updates["alpha_vantage_key"] else None
        if "nibss_api_key" in updates:
            config.nibss_api_key_enc = encryption.encrypt(updates["nibss_api_key"]) if updates["nibss_api_key"] else None
        if "cbn_openapi_url" in updates:
            config.cbn_openapi_url = updates["cbn_openapi_url"]
        if "ngx_api_url" in updates:
            config.ngx_api_url = updates["ngx_api_url"]
        if "use_global_model" in updates:
            config.use_global_model = updates["use_global_model"]
        if "alpha_strategy_type" in updates:
            config.alpha_strategy_type = updates["alpha_strategy_type"]
        config.updated_at = datetime.now(timezone.utc)
        db.commit()
        # Invalidate cache
        self.redis.delete(f"tenant_config:{tenant}")
        logger.info(f"Tenant config updated for {tenant}")
