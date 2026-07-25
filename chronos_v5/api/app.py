# chronos_v5/api/app.py
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi_limiter import FastAPILimiter
import redis.asyncio as aioredis
import redis
import asyncio
import os
import uuid
import bcrypt
import secrets
import httpx
from datetime import datetime, timezone
from chronos_v5.config import Config
from chronos_v5.api.middleware import CorrelationIdMiddleware
from chronos_v5.api.routers import (
    trade, collateral, risk, backtest, model, audit, dashboard, pricing, execution, nibss, websocket
)
from chronos_v5.api.routers import auth, admin, dashboard_tenant, tenant_config
from chronos_v5.logger_setup import logger
from prometheus_client import generate_latest, REGISTRY
from fastapi.responses import Response
from chronos_v5.database import SyncSessionLocal
from chronos_v5.nigeria_adapter import nigeria
from chronos_v5.models import User, APIKey
from sqlalchemy import text

app = FastAPI(
    title="Chronos v5.2 - Full Production Bank Edition",
    version="5.2.1",
    description="Enterprise Settlement Optimizer with Alpha & Real-Time Risk",
    docs_url="/docs" if Config.ENV != "production" else None,
    redoc_url=None
)

if Config.ENV == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=Config.ALLOWED_HOSTS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if Config.ENV == "development" else Config.ALLOWED_HOSTS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(CorrelationIdMiddleware)

if Config.OTEL_ENABLED:
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        provider = TracerProvider()
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=Config.OTEL_ENDPOINT))
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry enabled")
    except ImportError as e:
        logger.warning(f"OpenTelemetry import failed: {e}")

# --- ROUTERS ---
app.include_router(trade.router, prefix="/trade", tags=["Trade"])
app.include_router(collateral.router, prefix="/collateral", tags=["Collateral"])
app.include_router(risk.router, prefix="/risk", tags=["Risk"])
app.include_router(backtest.router, prefix="/backtest", tags=["Backtest"])
app.include_router(model.router, prefix="/model", tags=["Model"])
app.include_router(audit.router, prefix="/audit", tags=["Audit"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(pricing.router, prefix="/pricing", tags=["Pricing"])
app.include_router(execution.router, prefix="/execution", tags=["Execution"])
app.include_router(nibss.router, prefix="/nibss", tags=["NIBSS"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(dashboard_tenant.router, prefix="/tenant", tags=["Tenant Dashboard"])
app.include_router(tenant_config.router, prefix="/tenant/config", tags=["Tenant Config"])

if Config.ENV != "production" or os.getenv("ADVANCED_FEATURES_ENABLED", "false").lower() == "true":
    try:
        from chronos_v5.advanced.api.routers import advanced
        app.include_router(advanced.router, prefix="/advanced", tags=["Advanced"])
        logger.info("Advanced API routes enabled")
    except ImportError as e:
        logger.warning(f"Advanced API not available: {e}")

# ============================================================
# SCHEMA DETECTION & TABLE CREATION
# ============================================================
USER_COLUMNS = []
PASSWORD_COLUMN = None

def detect_user_columns():
    global USER_COLUMNS, PASSWORD_COLUMN
    db = SyncSessionLocal()
    try:
        result = db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='users'
        """))
        USER_COLUMNS = [row[0] for row in result.fetchall()]
        logger.info(f"Detected columns in users table: {USER_COLUMNS}")
        for col in ["password_hash", "hashed_password", "password", "pw_hash"]:
            if col in USER_COLUMNS:
                PASSWORD_COLUMN = col
                logger.info(f"Using password column: {PASSWORD_COLUMN}")
                break
        if PASSWORD_COLUMN is None:
            for col in USER_COLUMNS:
                if "password" in col.lower():
                    PASSWORD_COLUMN = col
                    logger.info(f"Using password column: {PASSWORD_COLUMN}")
                    break
    except Exception as e:
        logger.error(f"Failed to detect columns: {e}")
    finally:
        db.close()

def ensure_api_keys_table():
    db = SyncSessionLocal()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL,
                key_prefix VARCHAR(20) NOT NULL,
                key_hash VARCHAR(255) NOT NULL,
                tenant VARCHAR(50) NOT NULL DEFAULT 'default',
                created_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP,
                last_used_at TIMESTAMP
            )
        """))
        db.commit()
        logger.info("✅ api_keys table ready")
    except Exception as e:
        logger.error(f"Failed to create api_keys table: {e}")
    finally:
        db.close()

# ============================================================
# ADMIN CREATION
# ============================================================
def ensure_admin_exists():
    if not USER_COLUMNS or PASSWORD_COLUMN is None:
        logger.warning("Cannot create admin – no column info available")
        return

    db = SyncSessionLocal()
    try:
        result = db.execute(text("SELECT id FROM users WHERE role = 'admin' LIMIT 1"))
        if result.fetchone():
            logger.info("Admin already exists.")
            return

        admin_email = os.getenv("ADMIN_EMAIL", "admin@chronos.local")
        admin_password = os.getenv("ADMIN_PASSWORD", "Admin123!")
        hashed = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
        admin_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        columns = [col for col in USER_COLUMNS if col in [
            "id", "email", PASSWORD_COLUMN, "full_name", "role", "tenant",
            "created_at", "is_active", "trial_expiry", "last_login"
        ]]
        placeholders = ", ".join([f":{col}" for col in columns])
        sql = f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders})"

        params = {
            "id": str(admin_id),
            "email": admin_email,
            PASSWORD_COLUMN: hashed,
            "full_name": "System Admin",
            "role": "admin",
            "tenant": "default",
            "created_at": now,
            "is_active": True,
            "trial_expiry": None,
            "last_login": None
        }
        params = {k: v for k, v in params.items() if k in columns}

        db.execute(text(sql), params)
        db.commit()
        logger.info(f"✅ Admin user created with email: {admin_email}")

        raw_key = secrets.token_urlsafe(32)
        api_key_id = uuid.uuid4()
        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
        db.execute(
            text("""
                INSERT INTO api_keys (id, user_id, key_prefix, key_hash, tenant, created_at)
                VALUES (:id, :user_id, :key_prefix, :key_hash, :tenant, :created_at)
            """),
            {
                "id": str(api_key_id),
                "user_id": str(admin_id),
                "key_prefix": raw_key[:12],
                "key_hash": key_hash,
                "tenant": "default",
                "created_at": now
            }
        )
        db.commit()
        logger.info(f"🔑 Admin API key: {raw_key}")
        logger.info("📋 Copy this key now – it will not be shown again.")
    except Exception as e:
        logger.error(f"Failed to create admin: {e}")
    finally:
        db.close()

# ============================================================
# SELF‑TEST (idempotency) – uses detected schema
# ============================================================
async def run_self_test():
    if not USER_COLUMNS or PASSWORD_COLUMN is None:
        logger.warning("Self‑test skipped – no column info")
        return False

    base_url = f"http://localhost:{os.getenv('PORT', '10000')}"
    db = SyncSessionLocal()
    try:
        test_email = f"self_test_{uuid.uuid4().hex[:8]}@chronos.local"
        test_user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        hashed = bcrypt.hashpw(b"temp_pass", bcrypt.gensalt()).decode()

        columns = [col for col in USER_COLUMNS if col in [
            "id", "email", PASSWORD_COLUMN, "full_name", "role", "tenant",
            "created_at", "is_active", "trial_expiry", "last_login"
        ]]
        placeholders = ", ".join([f":{col}" for col in columns])
        sql = f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders})"

        params = {
            "id": str(test_user_id),
            "email": test_email,
            PASSWORD_COLUMN: hashed,
            "full_name": "Self Test",
            "role": "user",
            "tenant": "default",
            "created_at": now,
            "is_active": True,
            "trial_expiry": None,
            "last_login": None
        }
        params = {k: v for k, v in params.items() if k in columns}
        db.execute(text(sql), params)

        raw_key = secrets.token_urlsafe(32)
        api_key_id = uuid.uuid4()
        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
        db.execute(
            text("""
                INSERT INTO api_keys (id, user_id, key_prefix, key_hash, tenant, created_at)
                VALUES (:id, :user_id, :key_prefix, :key_hash, :tenant, :created_at)
            """),
            {
                "id": str(api_key_id),
                "user_id": str(test_user_id),
                "key_prefix": raw_key[:12],
                "key_hash": key_hash,
                "tenant": "default",
                "created_at": now
            }
        )
        db.commit()
        db.close()
    except Exception as e:
        db.close()
        logger.error(f"Self‑test DB setup failed: {e}")
        return False

    logger.info(f"Self‑test: created temporary user {test_email}")

    async def send_trade(client, idempotency_key):
        payload = {
            "id": str(uuid.uuid4()),
            "desk": "SELF_TEST",
            "counterparty_id": "SELF",
            "currency": "NGN",
            "notional": 1000,
            "settle_date": "2026-12-31T00:00:00",
            "idempotency_key": idempotency_key
        }
        resp = await client.post(
            f"{base_url}/trade/ingest_sync",
            json=payload,
            headers={"X-API-Key": raw_key, "X-Tenant": "default"}
        )
        return resp.status_code, resp.json()

    idempotency_key = f"self_test_{uuid.uuid4().hex}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [send_trade(client, idempotency_key) for _ in range(50)]
        results = await asyncio.gather(*tasks)

    successes = [r[1] for r in results if r[0] == 200]
    ingested = [r[1] for r in successes if r[1].get("status") == "INGESTED"]
    duplicates = [r[1] for r in successes if r[1].get("status") == "DUPLICATE"]

    passed = len(ingested) == 1 and len(duplicates) == 49
    logger.info(f"Self‑test: {len(ingested)} INGESTED, {len(duplicates)} DUPLICATE → {'PASS' if passed else 'FAIL'}")
    return passed

# ============================================================
# LIFECYCLE EVENTS
# ============================================================
@app.on_event("startup")
async def startup():
    # --- Ensure api_keys table exists ---
    ensure_api_keys_table()

    # --- Detect actual schema ---
    detect_user_columns()

    # --- Admin creation ---
    ensure_admin_exists()

    # --- Rate limiter ---
    if Config.ENV == "test":
        logger.info("Rate limiter disabled in test mode")
    else:
        redis_conn = await aioredis.from_url(Config.REDIS_URL, decode_responses=True)
        await FastAPILimiter.init(redis_conn)
        logger.info("FastAPI-Limiter initialized with async Redis")

    if Config.ASYNC_DB:
        from chronos_v5.database import async_database
        if async_database:
            await async_database.connect()
            logger.info("Async DB connected")

    # --- Self‑test (only if explicitly enabled) ---
    if os.getenv("RUN_SELFTEST", "false").lower() == "true":
        try:
            passed = await run_self_test()
            if not passed:
                logger.error("⚠️ Self‑test FAILED – idempotency broken!")
            else:
                logger.info("✅ Self‑test PASSED – idempotency works.")
        except Exception as e:
            logger.error(f"Self‑test error: {e}")

    asyncio.create_task(nigeria.connect_ngx_websocket())

@app.on_event("shutdown")
async def shutdown():
    if Config.ASYNC_DB:
        from chronos_v5.database import async_database
        if async_database:
            await async_database.disconnect()

@app.get("/health")
def health(request: Request):
    try:
        db = SyncSessionLocal()
        db.execute(text("SELECT 1"))
        db_status = "OK"
    except Exception as e:
        db_status = f"ERROR: {e}"
    return {
        "status": "OK",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "5.2.1",
        "db": db_status,
        "correlation_id": request.state.correlation_id if hasattr(request.state, 'correlation_id') else 'N/A'
    }

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(REGISTRY), media_type="text/plain")
