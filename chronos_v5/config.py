# chronos_v5/config.py
import os
import base64
import warnings
import secrets
from typing import List, Optional
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

class Config:
    # ===== CORE =====
    DB_ENGINE = os.getenv("CHRONOS_DB_ENGINE", "postgresql")
    DB_HOST = os.getenv("CHRONOS_DB_HOST", "localhost")
    DB_PORT = os.getenv("CHRONOS_DB_PORT", "5432")
    DB_USER = os.getenv("CHRONOS_DB_USER", "chronos")
    DB_PASS = os.getenv("CHRONOS_DB_PASS", "chronos")
    DB_NAME = os.getenv("CHRONOS_DB_NAME", "chronos")
    SQLITE_PATH = os.getenv("CHRONOS_SQLITE_PATH", "./chronos.db")
    DATABASE_URL = os.getenv("DATABASE_URL", None)
    DB_READ_REPLICA_URL = os.getenv("DB_READ_REPLICA_URL", None)
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "50"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "100"))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    # ===== REDIS & CACHE =====
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "300"))
    REDIS_SENTINEL = os.getenv("REDIS_SENTINEL", "")
    REDIS_SENTINEL_MASTER = os.getenv("REDIS_SENTINEL_MASTER", "mymaster")

    # ===== CELERY =====
    _base_redis = REDIS_URL.rstrip('/')
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", f"{_base_redis}/1")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", f"{_base_redis}/2")
    CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
    CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "600"))
    CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "540"))

    # ===== SECURITY =====
    API_KEY = os.getenv("CHRONOS_API_KEY", None)
    ENV = os.getenv("CHRONOS_ENV", "development")
    RATE_LIMIT = os.getenv("CHRONOS_RATE_LIMIT", "100 per minute")
    ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()] or []
    SECRET_KEY = os.getenv("SECRET_KEY", None)
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", None)
    RUN_SELFTEST = os.getenv("RUN_SELFTEST", "false").lower() == "true"

    # ===== AUTH & PASSWORD POLICY =====
    JWT_SECRET = os.getenv("JWT_SECRET", None)
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
    ADMIN_EMAILS = [e.strip() for e in os.getenv("ADMIN_EMAILS", "admin@chronos.local").split(",") if e.strip()]
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
    PASSWORD_REQUIRE_UPPER = os.getenv("PASSWORD_REQUIRE_UPPER", "true").lower() == "true"
    PASSWORD_REQUIRE_LOWER = os.getenv("PASSWORD_REQUIRE_LOWER", "true").lower() == "true"
    PASSWORD_REQUIRE_DIGIT = os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"
    PASSWORD_REQUIRE_SPECIAL = os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"
    AUTH_RATE_LIMIT_LOGIN = os.getenv("AUTH_RATE_LIMIT_LOGIN", "10 per minute")
    AUTH_RATE_LIMIT_REGISTER = os.getenv("AUTH_RATE_LIMIT_REGISTER", "5 per hour")
    ADMIN_BOOTSTRAP_MODE = os.getenv("ADMIN_BOOTSTRAP_MODE", "disabled")

    # ===== HSM =====
    HSM_ENABLED = os.getenv("HSM_ENABLED", "false").lower() == "true"
    HSM_PKCS11_LIB = os.getenv("HSM_PKCS11_LIB", "/usr/lib/libcloudhsm_pkcs11.so")
    HSM_TOKEN_LABEL = os.getenv("HSM_TOKEN_LABEL", "chronos")
    HSM_PIN = os.getenv("HSM_PIN", "")

    # ===== MODEL =====
    MODEL_PATH = os.getenv("CHRONOS_MODEL", "./model_v5.pkl")
    MODEL_BACKUP_PATH = os.getenv("MODEL_BACKUP_PATH", "./model_backup.pkl")
    MODEL_RETRAIN_INTERVAL = int(os.getenv("MODEL_RETRAIN_INTERVAL", "3600"))
    ONLINE_LEARNING_BATCH_SIZE = int(os.getenv("ONLINE_LEARNING_BATCH_SIZE", "100"))
    CONCEPT_DRIFT_THRESHOLD = float(os.getenv("CONCEPT_DRIFT_THRESHOLD", "0.05"))
    MODEL_STORAGE_BACKEND = os.getenv("MODEL_STORAGE_BACKEND", "local")
    MODEL_STORAGE_BUCKET = os.getenv("MODEL_STORAGE_BUCKET", "")
    MODEL_STORAGE_PREFIX = os.getenv("MODEL_STORAGE_PREFIX", "models/")
    AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY", "")
    AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY", "")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    GCS_CREDENTIALS = os.getenv("GCS_CREDENTIALS", "")

    # ===== FINANCIAL DEFAULTS =====
    DEFAULT_FAIL_RATE = float(os.getenv("DEFAULT_FAIL_RATE", "0.15"))
    REHYPOTHECATION_YIELD = float(os.getenv("REHYPOTHECATION_YIELD", "0.18"))
    EMERGENCY_BORROW_RATE = float(os.getenv("EMERGENCY_BORROW_RATE", "0.26"))
    SCAN_INTERVAL_SEC = int(os.getenv("SCAN_INTERVAL_SEC", "60"))

    # ===== MARKET DATA =====
    MARKET_DATA_PROVIDER = os.getenv("MARKET_DATA_PROVIDER", "bloomberg")
    BLOOMBERG_API_URL = os.getenv("BLOOMBERG_API_URL", "https://api.bloomberg.com/v1")
    BLOOMBERG_API_KEY = os.getenv("BLOOMBERG_API_KEY", "")
    REUTERS_API_URL = os.getenv("REUTERS_API_URL", "https://api.refinitiv.com/v1")
    REUTERS_API_KEY = os.getenv("REUTERS_API_KEY", "")
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    YAHOO_FINANCE_ENABLED = os.getenv("YAHOO_FINANCE_ENABLED", "false").lower() == "true"
    MARKET_DATA_TIMEOUT = int(os.getenv("MARKET_DATA_TIMEOUT", "5"))
    CBN_OPENAPI_URL = os.getenv("CBN_OPENAPI_URL", "https://api.cbn.gov.ng/rates")
    NGX_API_URL = os.getenv("NGX_API_URL", "https://api.ngxgroup.com/api/v1")
    NGX_WEBSOCKET = os.getenv("NGX_WEBSOCKET", "wss://stream.ngxgroup.com/ws")

    # ===== REAL NIBSS =====
    NIBSS_API_URL = os.getenv("NIBSS_API_URL", "https://api.nibss.gov.ng/v1")
    NIBSS_API_KEY = os.getenv("NIBSS_API_KEY", "")
    NIBSS_TIMEOUT = int(os.getenv("NIBSS_TIMEOUT", "10"))
    NIBSS_MAX_RETRIES = int(os.getenv("NIBSS_MAX_RETRIES", "3"))
    NIBSS_RETRY_DELAY = int(os.getenv("NIBSS_RETRY_DELAY", "2"))

    # ===== LOGGING =====
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_JSON = os.getenv("LOG_JSON", "false").lower() == "true" or (os.getenv("CHRONOS_ENV", "development") == "production")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "default")
    LOG_FILE = os.getenv("LOG_FILE", "chronos.log")
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "104857600"))
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "10"))
    LOG_CORRELATION_ID = os.getenv("LOG_CORRELATION_ID", "true").lower() == "true"

    # ===== EXECUTION =====
    EXECUTION_ENGINE_ENABLED = os.getenv("EXECUTION_ENGINE_ENABLED", "false").lower() == "true"
    FIX_ENGINE_URL = os.getenv("FIX_ENGINE_URL", "fix://localhost:9000")
    FIX_SENDER_COMP_ID = os.getenv("FIX_SENDER_COMP_ID", "CHRONOS")
    FIX_TARGET_COMP_ID = os.getenv("FIX_TARGET_COMP_ID", "BROKER")
    EXECUTION_GATEWAY_API_KEY = os.getenv("EXECUTION_GATEWAY_API_KEY", "")
    EXECUTION_MAX_RETRIES = int(os.getenv("EXECUTION_MAX_RETRIES", "3"))
    EXECUTION_RETRY_DELAY = int(os.getenv("EXECUTION_RETRY_DELAY", "2"))

    # ===== PRICING =====
    PRICING_SPREAD_BASELINE = float(os.getenv("PRICING_SPREAD_BASELINE", "0.03"))
    MIN_FEE_PER_TRADE = float(os.getenv("MIN_FEE_PER_TRADE", "5000.0"))

    # ===== RISK =====
    CAPITAL_REQUIREMENT_SA_CCR = float(os.getenv("CAPITAL_REQUIREMENT_SA_CCR", "0.08"))
    VAR_CONFIDENCE = float(os.getenv("VAR_CONFIDENCE", "0.99"))
    VAR_HORIZON = int(os.getenv("VAR_HORIZON", "1"))
    STRESS_SCENARIOS = [s.strip() for s in os.getenv("STRESS_SCENARIOS", "2008,COVID,NIGERIA_2020").split(",") if s.strip()]
    RISK_FALLBACK_VOLATILITY = float(os.getenv("RISK_FALLBACK_VOLATILITY", "0.02"))
    RISK_DAILY_VOL_SCALING = float(os.getenv("RISK_DAILY_VOL_SCALING", "0.01"))

    # ===== SYNTHETIC & CYCLE =====
    SYNTHETIC_TRADES_COUNT = int(os.getenv("SYNTHETIC_TRADES_COUNT", "50000"))
    MAX_CYCLE_DEPTH = int(os.getenv("MAX_CYCLE_DEPTH", "20"))
    MAX_CYCLES_RETURNED = int(os.getenv("MAX_CYCLES_RETURNED", "1000"))

    # ===== DATA SOURCES =====
    REAL_DATA_CSV_PATH = os.getenv("REAL_DATA_CSV_PATH", "")
    REAL_DATA_DB_TABLE = os.getenv("REAL_DATA_DB_TABLE", "historical_settlements")

    # ===== HAIRCUT =====
    HAIRCUT_BASELINE = float(os.getenv("HAIRCUT_BASELINE", "0.02"))
    HAIRCUT_VOLATILITY_SCALE = float(os.getenv("HAIRCUT_VOLATILITY_SCALE", "0.5"))
    COLLATERAL_TYPES = [c.strip() for c in os.getenv("COLLATERAL_TYPES", "CASH,TBILL,BOND,EQUITY").split(",") if c.strip()]

    # ===== CIRCUIT BREAKER =====
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
    CIRCUIT_BREAKER_TIMEOUT_SEC = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT_SEC", "60"))

    # ===== ALERTING =====
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
    PAGERDUTY_URL = os.getenv("PAGERDUTY_URL", "")
    ALERT_MIN_SEVERITY = os.getenv("ALERT_MIN_SEVERITY", "WARNING")
    WEBHOOK_RETRY_COUNT = int(os.getenv("WEBHOOK_RETRY_COUNT", "3"))

    # ===== OBSERVABILITY =====
    OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    OTEL_ENDPOINT = os.getenv("OTEL_ENDPOINT", "http://localhost:4317")
    OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "chronos")
    PROFILING_ENABLED = os.getenv("PROFILING_ENABLED", "false").lower() == "true"

    # ===== ENCRYPTION =====
    ENCRYPT_SENSITIVE_FIELDS = os.getenv("ENCRYPT_SENSITIVE_FIELDS", "true").lower() == "true"
    ALLOW_INSECURE = os.getenv("ALLOW_INSECURE", "false").lower() == "true"

    # ===== MULTI-TENANCY =====
    TENANT_HEADER = os.getenv("TENANT_HEADER", "X-Tenant")
    DEFAULT_TENANT = os.getenv("DEFAULT_TENANT", "default")

    # ===== CACHE & DB MODE =====
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    ASYNC_DB = os.getenv("ASYNC_DB", "true").lower() == "true"

    # ===== SSL / CERTS =====
    LETSENCRYPT_ENABLED = os.getenv("LETSENCRYPT_ENABLED", "false").lower() == "true"
    LETSENCRYPT_DOMAIN = os.getenv("LETSENCRYPT_DOMAIN", "")
    LETSENCRYPT_EMAIL = os.getenv("LETSENCRYPT_EMAIL", "")

    # ===== PERFORMANCE FEE =====
    PERFORMANCE_FEE_ENABLED = os.getenv("PERFORMANCE_FEE_ENABLED", "true").lower() == "true"
    PERFORMANCE_FEE_PERCENT = float(os.getenv("PERFORMANCE_FEE_PERCENT", "0.20"))

    # ===== ALPHA & REHYPO =====
    ALPHA_STRATEGY_ENABLED = os.getenv("ALPHA_STRATEGY_ENABLED", "false").lower() == "true"
    ALPHA_STRATEGY_TYPE = os.getenv("ALPHA_STRATEGY_TYPE", "mean_reversion")
    ALPHA_STRATEGY_ASSETS = [a.strip() for a in os.getenv("ALPHA_STRATEGY_ASSETS", "NGX:ALLSHARE").split(",") if a.strip()]

    REHYPO_OPTIMIZER_ENABLED = os.getenv("REHYPO_OPTIMIZER_ENABLED", "true").lower() == "true"
    REHYPO_OPTIMIZER_INTERVAL = int(os.getenv("REHYPO_OPTIMIZER_INTERVAL", "300"))

    # ===== DB BACKUP =====
    DB_BACKUP_ENABLED = os.getenv("DB_BACKUP_ENABLED", "false").lower() == "true"
    DB_BACKUP_PATH = os.getenv("DB_BACKUP_PATH", "/backups")
    DB_BACKUP_INTERVAL = int(os.getenv("DB_BACKUP_INTERVAL", "86400"))
    BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
    BACKUP_COMPRESSION = os.getenv("BACKUP_COMPRESSION", "gzip").lower()

    # ===== AUTOMATION =====
    AUTOMATION_ENABLED = os.getenv("AUTOMATION_ENABLED", "true").lower() == "true"
    AUTOMATION_SCHEDULE_DEFAULT = os.getenv("AUTOMATION_SCHEDULE_DEFAULT", "daily 02:00")

    # ===== MONITORING =====
    MONITORING_QUEUE_POLL_INTERVAL = int(os.getenv("MONITORING_QUEUE_POLL_INTERVAL", "10"))
    MONITORING_LOG_TAIL_LINES = int(os.getenv("MONITORING_LOG_TAIL_LINES", "100"))

    # ===== WEBHOOKS =====
    WEBHOOK_TIMEOUT_SEC = int(os.getenv("WEBHOOK_TIMEOUT_SEC", "5"))
    WEBHOOK_RETRY_COUNT = int(os.getenv("WEBHOOK_RETRY_COUNT", "3"))

    # ===== SECRET STORE =====
    SECRET_STORE_URL = os.getenv("SECRET_STORE_URL", "")

    # ===== TENANT DEFAULTS =====
    DEFAULT_TENANT_CONFIG = {
        "performance_fee_percent": 0.20,
        "bloomberg_api_key": "",
        "reuters_api_key": "",
        "alpha_vantage_key": "",
        "nibss_api_key": "",
        "cbn_openapi_url": CBN_OPENAPI_URL,
        "ngx_api_url": NGX_API_URL,
        "use_global_model": True,
        "alpha_strategy_type": ALPHA_STRATEGY_TYPE,
    }

    @classmethod
    def _derive_encryption_key_from_secret(cls, secret: str) -> str:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'chronos_secure_salt_v1',
            iterations=200_000
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
        return key.decode()

    @classmethod
    def get_database_url(cls) -> str:
        if cls.DATABASE_URL:
            return cls.DATABASE_URL
        proto = cls.DB_ENGINE
        user = cls.DB_USER
        password = cls.DB_PASS
        host = cls.DB_HOST
        port = cls.DB_PORT
        name = cls.DB_NAME
        return f"{proto}://{user}:{password}@{host}:{port}/{name}"

    @classmethod
    def _base64_key_valid(cls, key: str) -> bool:
        try:
            decoded = base64.urlsafe_b64decode(key.encode())
            return len(decoded) >= 32
        except Exception:
            return False

    @classmethod
    def _maybe_fetch_from_secret_store(cls, name: str) -> Optional[str]:
        url = cls.SECRET_STORE_URL or ""
        if not url:
            return None

        if url.startswith("aws://") or url.startswith("secretsmanager://"):
            try:
                import boto3
                client = boto3.client('secretsmanager')
                resp = client.get_secret_value(SecretId=name)
                if 'SecretString' in resp and resp['SecretString']:
                    return resp['SecretString']
                elif 'SecretBinary' in resp and resp['SecretBinary']:
                    return base64.b64decode(resp['SecretBinary']).decode()
            except Exception as e:
                warnings.warn(f"AWS Secrets fetch failed for {name}: {e}")
                return None

        if url.startswith("vault://") or url.startswith("vaults://"):
            try:
                import hvac
                tail = url.split("://", 1)[1]
                vault_addr = os.getenv("VAULT_ADDR") or f"https://{tail.split('/')[0]}"
                client = hvac.Client(url=vault_addr, token=os.getenv("VAULT_TOKEN"))
                read = client.secrets.kv.v2.read_secret_version(path=name)
                data = read.get("data", {}).get("data", {})
                if "value" in data:
                    return data["value"]
                if data:
                    return next(iter(data.values()))
            except Exception as e:
                warnings.warn(f"Vault fetch failed for {name}: {e}")
                return None

        warnings.warn(f"SECRET_STORE_URL configured but scheme not supported or fetch failed for {name}")
        return None

    @classmethod
    def get_logging_config(cls):
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s"
                },
                "json": {
                    "format": "%(message)s"
                }
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "formatter": "json" if cls.LOG_JSON else "default",
                    "level": cls.LOG_LEVEL,
                },
            },
            "root": {
                "handlers": ["stdout"],
                "level": cls.LOG_LEVEL,
            }
        }

    @classmethod
    def validate(cls):
        errors: List[str] = []

        if not cls.DATABASE_URL:
            cls.DATABASE_URL = cls.get_database_url()
            if cls.ENV == "production" and ("localhost" in cls.DATABASE_URL or "127.0.0.1" in cls.DATABASE_URL):
                errors.append("DATABASE_URL must be set to a production-ready host (not localhost/127.0.0.1).")

        if not cls.SECRET_KEY:
            secret = cls._maybe_fetch_from_secret_store("SECRET_KEY")
            if secret:
                cls.SECRET_KEY = secret
            else:
                errors.append("SECRET_KEY is not set. Provide a strong SECRET_KEY (>=32 chars) via env or secret store.")

        if cls.SECRET_KEY and len(cls.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be at least 32 characters long for production security.")

        if not cls.ENCRYPTION_KEY:
            fetched = cls._maybe_fetch_from_secret_store("ENCRYPTION_KEY")
            if fetched:
                cls.ENCRYPTION_KEY = fetched
            elif cls.SECRET_KEY:
                cls.ENCRYPTION_KEY = cls._derive_encryption_key_from_secret(cls.SECRET_KEY)
                warnings.warn("ENCRYPTION_KEY was not set explicitly. Derived from SECRET_KEY as a fallback; set ENCRYPTION_KEY in secret store for rotation safety.")
            else:
                errors.append("ENCRYPTION_KEY is not set and cannot be derived (SECRET_KEY missing).")

        if cls.ENCRYPTION_KEY and not cls._base64_key_valid(cls.ENCRYPTION_KEY):
            errors.append("ENCRYPTION_KEY must be a base64 URL-safe encoded key representing at least 32 bytes.")

        if not cls.JWT_SECRET:
            fetched = cls._maybe_fetch_from_secret_store("JWT_SECRET")
            if fetched:
                cls.JWT_SECRET = fetched
            elif cls.SECRET_KEY:
                if cls.ENV == "production":
                    errors.append("JWT_SECRET is not set explicitly in production. Set JWT_SECRET to a dedicated secret (>=32 chars).")
                else:
                    cls.JWT_SECRET = cls.SECRET_KEY
                    warnings.warn("JWT_SECRET not set; using SECRET_KEY as fallback for non-production environments.")
            else:
                errors.append("JWT_SECRET not set and cannot be derived (SECRET_KEY missing).")

        if cls.JWT_SECRET and len(cls.JWT_SECRET) < 32:
            errors.append("JWT_SECRET must be at least 32 characters long.")

        if not cls.API_KEY:
            fetched = cls._maybe_fetch_from_secret_store("CHRONOS_API_KEY")
            if fetched:
                cls.API_KEY = fetched
            else:
                errors.append("CHRONOS_API_KEY is not set. This service requires an API key for internal admin operations.")

        if cls.ENV == "production":
            if not cls.ALLOWED_HOSTS:
                errors.append("ALLOWED_HOSTS must be set for production to avoid open host access (do not use '*').")
            if cls.REDIS_URL.startswith("redis://localhost") or "127.0.0.1" in cls.REDIS_URL:
                errors.append("REDIS_URL should point to a managed Redis instance in production, not localhost.")
            if not cls.NIBSS_API_KEY:
                errors.append("NIBSS_API_KEY is required in production.")
            if cls.RUN_SELFTEST:
                errors.append("RUN_SELFTEST must be false in production. Self-tests can interfere with live systems.")
            if cls.ADMIN_BOOTSTRAP_MODE.lower() == "env":
                if not cls.ADMIN_EMAILS:
                    errors.append("ADMIN_EMAILS must be specified when ADMIN_BOOTSTRAP_MODE=env.")
            if cls.HSM_ENABLED and not cls.HSM_PIN:
                errors.append("HSM_ENABLED is true but HSM_PIN is not set. Provide a secure PIN via secret store.")

        if cls.LETSENCRYPT_ENABLED:
            if not cls.LETSENCRYPT_DOMAIN:
                errors.append("LETSENCRYPT_DOMAIN must be set when LETSENCRYPT_ENABLED=true.")
            if not cls.LETSENCRYPT_EMAIL:
                errors.append("LETSENCRYPT_EMAIL must be set when LETSENCRYPT_ENABLED=true.")

        if cls.EXECUTION_ENGINE_ENABLED and not cls.EXECUTION_GATEWAY_API_KEY:
            warnings.warn("EXECUTION_ENGINE_ENABLED is true but EXECUTION_GATEWAY_API_KEY is not set. Execution may fail without proper credentials.")

        if cls.MODEL_STORAGE_BACKEND.lower() == "s3":
            if not (cls.AWS_ACCESS_KEY and cls.AWS_SECRET_KEY and cls.MODEL_STORAGE_BUCKET):
                errors.append("MODEL_STORAGE_BACKEND=s3 requires AWS_ACCESS_KEY, AWS_SECRET_KEY, and MODEL_STORAGE_BUCKET to be set.")

        if cls.HSM_ENABLED and (not cls.HSM_PIN or cls.HSM_PIN in ("changeme", "1234", "0000")):
            errors.append("HSM_PIN appears to be a weak default. Provide a strong PIN via secret store.")

        if cls.DB_POOL_SIZE <= 0:
            errors.append("DB_POOL_SIZE must be > 0")
        if cls.DB_MAX_OVERFLOW < 0:
            errors.append("DB_MAX_OVERFLOW must be >= 0")

        if errors:
            raise RuntimeError("Configuration validation failed:\n - " + "\n - ".join(errors))

Config.validate()
