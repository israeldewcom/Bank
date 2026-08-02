# chronos_v5/config.py
import os
import base64
import secrets
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

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
    REDIS_SENTINEL = os.getenv("REDIS_SENTINEL", None)
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
    ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
    SECRET_KEY = os.getenv("SECRET_KEY", None)
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", None)

    # ===== NEW AUTH SETTINGS =====
    JWT_SECRET = os.getenv("JWT_SECRET", None)
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
    ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "admin@chronos.local").split(",")
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
    PASSWORD_REQUIRE_UPPER = os.getenv("PASSWORD_REQUIRE_UPPER", "true").lower() == "true"
    PASSWORD_REQUIRE_LOWER = os.getenv("PASSWORD_REQUIRE_LOWER", "true").lower() == "true"
    PASSWORD_REQUIRE_DIGIT = os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"
    PASSWORD_REQUIRE_SPECIAL = os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"
    AUTH_RATE_LIMIT_LOGIN = os.getenv("AUTH_RATE_LIMIT_LOGIN", "10 per minute")
    AUTH_RATE_LIMIT_REGISTER = os.getenv("AUTH_RATE_LIMIT_REGISTER", "5 per hour")

    # ===== HSM =====
    HSM_ENABLED = os.getenv("HSM_ENABLED", "false").lower() == "true"
    HSM_PKCS11_LIB = os.getenv("HSM_PKCS11_LIB", "/usr/lib/libcloudhsm_pkcs11.so")
    HSM_TOKEN_LABEL = os.getenv("HSM_TOKEN_LABEL", "chronos")
    HSM_PIN = os.getenv("HSM_PIN", "changeme")

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
    LOG_JSON = os.getenv("LOG_JSON", "false").lower() == "true"
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
    STRESS_SCENARIOS = os.getenv("STRESS_SCENARIOS", "2008,COVID,NIGERIA_2020").split(",")
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
    COLLATERAL_TYPES = os.getenv("COLLATERAL_TYPES", "CASH,TBILL,BOND,EQUITY").split(",")

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

    # ===== CACHE =====
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    ASYNC_DB = os.getenv("ASYNC_DB", "true").lower() == "true"

    # ===== SSL =====
    LETSENCRYPT_ENABLED = os.getenv("LETSENCRYPT_ENABLED", "false").lower() == "true"
    LETSENCRYPT_DOMAIN = os.getenv("LETSENCRYPT_DOMAIN", "")
    LETSENCRYPT_EMAIL = os.getenv("LETSENCRYPT_EMAIL", "")

    # ===== PERFORMANCE FEE =====
    PERFORMANCE_FEE_ENABLED = os.getenv("PERFORMANCE_FEE_ENABLED", "true").lower() == "true"
    PERFORMANCE_FEE_PERCENT = float(os.getenv("PERFORMANCE_FEE_PERCENT", "0.20"))

    # ===== NEW: ALPHA STRATEGY =====
    ALPHA_STRATEGY_ENABLED = os.getenv("ALPHA_STRATEGY_ENABLED", "false").lower() == "true"
    ALPHA_STRATEGY_TYPE = os.getenv("ALPHA_STRATEGY_TYPE", "mean_reversion")
    ALPHA_STRATEGY_ASSETS = os.getenv("ALPHA_STRATEGY_ASSETS", "NGX:ALLSHARE").split(",")

    # ===== NEW: REHYPOTHECATION OPTIMIZER =====
    REHYPO_OPTIMIZER_ENABLED = os.getenv("REHYPO_OPTIMIZER_ENABLED", "true").lower() == "true"
    REHYPO_OPTIMIZER_INTERVAL = int(os.getenv("REHYPO_OPTIMIZER_INTERVAL", "300"))

    # ===== DB BACKUP =====
    DB_BACKUP_ENABLED = os.getenv("DB_BACKUP_ENABLED", "false").lower() == "true"
    DB_BACKUP_PATH = os.getenv("DB_BACKUP_PATH", "/backups")
    DB_BACKUP_INTERVAL = int(os.getenv("DB_BACKUP_INTERVAL", "86400"))

    @classmethod
    def validate(cls):
        errors = []

        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is not set")

        if not cls.SECRET_KEY:
            errors.append("SECRET_KEY is not set (must be at least 32 characters)")
        elif len(cls.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be at least 32 characters long")

        if not cls.ENCRYPTION_KEY:
            if cls.SECRET_KEY:
                from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                from cryptography.hazmat.primitives import hashes
                import base64
                kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b'chronos_salt', iterations=100000)
                key = base64.urlsafe_b64encode(kdf.derive(cls.SECRET_KEY.encode()))
                cls.ENCRYPTION_KEY = key.decode()
            else:
                errors.append("ENCRYPTION_KEY is not set and cannot be derived (SECRET_KEY missing)")

        if not cls.JWT_SECRET:
            if cls.SECRET_KEY:
                cls.JWT_SECRET = cls.SECRET_KEY
                import warnings
                warnings.warn("JWT_SECRET was not set explicitly; using SECRET_KEY as JWT_SECRET. "
                              "For production, set JWT_SECRET separately.")
            else:
                errors.append("JWT_SECRET is not set and cannot be derived (SECRET_KEY missing)")

        if cls.ENV == "production":
            if cls.JWT_SECRET == cls.SECRET_KEY:
                errors.append("In production, JWT_SECRET must be explicitly set and different from SECRET_KEY. "
                              "Please set JWT_SECRET in your .env file.")
            elif not cls.JWT_SECRET or len(cls.JWT_SECRET) < 32:
                errors.append("JWT_SECRET must be at least 32 characters long in production.")

        if cls.JWT_SECRET and len(cls.JWT_SECRET) < 32:
            errors.append("JWT_SECRET must be at least 32 characters long (derived from SECRET_KEY or set explicitly)")

        if not cls.API_KEY:
            errors.append("CHRONOS_API_KEY is not set")

        if not cls.REDIS_URL:
            errors.append("REDIS_URL is not set")

        if cls.ENV not in ("development", "staging", "production", "test"):
            errors.append(f"CHRONOS_ENV must be one of: development, staging, production, test (got {cls.ENV})")

        if cls.ENV == "production" and not cls.NIBSS_API_KEY:
            errors.append("NIBSS_API_KEY is required in production")

        if errors:
            raise RuntimeError("Configuration validation failed:\n - " + "\n - ".join(errors))

Config.validate()
