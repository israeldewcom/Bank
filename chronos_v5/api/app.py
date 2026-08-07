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
from datetime import datetime, timezone, timedelta
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
from sqlalchemy import text, exc

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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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
TRADES_COLUMNS = []

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

def detect_trades_columns():
    global TRADES_COLUMNS
    db = SyncSessionLocal()
    try:
        result = db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='trades'
        """))
        TRADES_COLUMNS = [row[0] for row in result.fetchall()]
        logger.info(f"Detected columns in trades table: {TRADES_COLUMNS}")
    except Exception as e:
        logger.error(f"Failed to detect trades columns: {e}")
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
        db.rollback()
    finally:
        db.close()

def ensure_tenant_configs_table():
    db = SyncSessionLocal()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS tenant_configs (
                tenant VARCHAR(50) PRIMARY KEY,
                performance_fee_percent FLOAT DEFAULT 0.20,
                bloomberg_api_key_enc TEXT,
                reuters_api_key_enc TEXT,
                alpha_vantage_key_enc TEXT,
                nibss_api_key_enc TEXT,
                cbn_openapi_url VARCHAR(255),
                ngx_api_url VARCHAR(255),
                use_global_model BOOLEAN DEFAULT TRUE,
                alpha_strategy_type VARCHAR(50),
                updated_at TIMESTAMP
            )
        """))
        db.commit()
        logger.info("✅ tenant_configs table ready")
    except Exception as e:
        logger.error(f"Failed to create tenant_configs table: {e}")
        db.rollback()
    finally:
        db.close()

# ============================================================
# ADMIN CREATION & DEVICE APPROVAL (FIXED)
# ============================================================
def ensure_admin_exists():
    if not USER_COLUMNS or PASSWORD_COLUMN is None:
        logger.warning("Cannot create admin – no column info available")
        return

    db = SyncSessionLocal()
    try:
        result = db.execute(text("SELECT id FROM users WHERE role = 'admin' LIMIT 1"))
        admin_row = result.fetchone()
        if not admin_row:
            admin_email = os.getenv("ADMIN_EMAIL", "admin@chronos.com")
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
            logger.info("🔑 Admin API key generated securely (not logged).")
            # Create approved device for admin
            _ensure_admin_device(db, str(admin_id))
        else:
            admin_id = admin_row[0]
            # Ensure device exists even if admin already existed
            _ensure_admin_device(db, str(admin_id))
    except Exception as e:
        logger.error(f"Failed to create admin: {e}")
        db.rollback()
    finally:
        db.close()

def _ensure_admin_device(db, admin_id):
    """Create an approved device for the admin if missing."""
    try:
        # Check if a device with fingerprint 'web-client' already exists for this admin
        result = db.execute(
            text("SELECT id FROM devices WHERE user_id = :uid AND device_fingerprint = 'web-client'"),
            {"uid": admin_id}
        )
        if not result.fetchone():
            db.execute(
                text("""
                    INSERT INTO devices (id, user_id, device_name, device_fingerprint, status, tenant, requested_at, approved_at)
                    VALUES (gen_random_uuid(), :uid, 'Default Web Client', 'web-client', 'approved', 'default', NOW(), NOW())
                """),
                {"uid": admin_id}
            )
            db.commit()
            logger.info(f"✅ Approved device 'web-client' created for admin {admin_id}")
        else:
            logger.debug(f"Admin device 'web-client' already exists for {admin_id}")
    except Exception as e:
        logger.error(f"Failed to ensure admin device: {e}")
        db.rollback()

# ============================================================
# DB‑BASED IDEMPOTENCY SELF‑TEST
# ============================================================
def run_self_test_db():
    if not TRADES_COLUMNS:
        logger.warning("Trades columns not detected – skipping self‑test.")
        return False

    db = SyncSessionLocal()
    try:
        idempotency_key = f"self_test_{uuid.uuid4().hex}"

        base_cols = ["id", "desk", "counterparty_id", "notional", "settle_date", "created_at", "status", "fail_probability", "idempotency_key"]
        optional_cols = ["instrument_type", "currency", "tenant"]
        insert_cols = [c for c in base_cols + optional_cols if c in TRADES_COLUMNS]
        placeholders = ", ".join([f":{c}" for c in insert_cols])
        sql = f"INSERT INTO trades ({', '.join(insert_cols)}) VALUES ({placeholders})"

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        settle_date = (datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None)

        params = {
            "id": str(uuid.uuid4()),
            "desk": "SELF_TEST",
            "counterparty_id": "SELF",
            "notional": 1000,
            "settle_date": settle_date,
            "created_at": now,
            "status": "PENDING",
            "fail_probability": 0.0,
            "idempotency_key": idempotency_key
        }
        if "instrument_type" in insert_cols:
            params["instrument_type"] = "TEST"
        if "currency" in insert_cols:
            params["currency"] = "NGN"
        if "tenant" in insert_cols:
            params["tenant"] = "default"

        db.execute(text(sql), params)
        db.commit()

        params2 = params.copy()
        params2["id"] = str(uuid.uuid4())
        try:
            db.execute(text(sql), params2)
            db.commit()
            logger.error("⚠️ Self‑test FAILED – duplicate insert succeeded!")
            return False
        except exc.IntegrityError as e:
            db.rollback()
            logger.info("Self‑test: duplicate insert correctly blocked (unique violation).")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Self‑test unexpected error: {e}")
            return False
    except Exception as e:
        logger.error(f"Self‑test DB setup failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

# ============================================================
# HTTP CONCURRENCY SELF‑TEST (background)
# ============================================================
async def run_http_concurrency_test():
    await asyncio.sleep(5)
    base_url = f"http://localhost:{os.getenv('PORT', '8000')}"

    db = SyncSessionLocal()
    try:
        password_col = PASSWORD_COLUMN or "password_hash"
        test_email = f"http_test_{uuid.uuid4().hex[:8]}@chronos.local"
        test_user_id = uuid.uuid4()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        hashed = bcrypt.hashpw(b"temp_pass", bcrypt.gensalt()).decode()

        columns = [col for col in USER_COLUMNS if col in [
            "id", "email", password_col, "full_name", "tenant",
            "created_at", "is_active", "trial_expiry", "last_login"
        ]]
        for col in ["status", "role"]:
            if col in USER_COLUMNS:
                columns.append(col)
        placeholders = ", ".join([f":{col}" for col in columns])
        sql = f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders})"

        params = {
            "id": str(test_user_id),
            "email": test_email,
            password_col: hashed,
            "full_name": "HTTP Self Test",
            "tenant": "default",
            "created_at": now,
            "is_active": True,
            "trial_expiry": None,
            "last_login": None
        }
        if "status" in columns:
            params["status"] = "approved"
        if "role" in columns:
            params["role"] = "user"
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
        logger.error(f"HTTP concurrency test DB setup failed: {e}")
        db.rollback()
        db.close()
        return

    logger.info(f"HTTP concurrency test: created temporary user {test_email}")

    async def send_trade(client, idempotency_key):
        payload = {
            "id": str(uuid.uuid4()),
            "desk": "CONCURRENCY_TEST",
            "counterparty_id": "SELF",
            "currency": "NGN",
            "notional": 1000,
            "settle_date": (datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None).isoformat(),
            "idempotency_key": idempotency_key
        }
        try:
            resp = await client.post(
                f"{base_url}/trade/ingest",
                json=payload,
                headers={"X-API-Key": raw_key, "X-Tenant": "default"},
                timeout=10.0
            )
            return resp.status_code, resp.json()
        except Exception as e:
            return 0, {"error": str(e)}

    idempotency_key = f"concurrent_{uuid.uuid4().hex}"
    start = datetime.now()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = [send_trade(client, idempotency_key) for _ in range(50)]
            results = await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"HTTP concurrency test gather failed: {e}")
        return
    elapsed = (datetime.now() - start).total_seconds()

    successes = [r[1] for r in results if r[0] == 200]
    ingested = [r[1] for r in successes if r[1].get("status") == "INGESTED"]
    duplicates = [r[1] for r in successes if r[1].get("status") == "DUPLICATE"]
    errors = [r[1] for r in results if r[0] != 200]

    logger.info(f"HTTP concurrency test completed in {elapsed:.2f}s: {len(ingested)} INGESTED, {len(duplicates)} DUPLICATE, {len(errors)} errors")
    if len(ingested) == 1 and len(duplicates) == 49 and len(errors) == 0:
        logger.info("✅ HTTP concurrency test PASSED – idempotency holds under load.")
    else:
        logger.error("⚠️ HTTP concurrency test FAILED – check duplicate handling.")

# ============================================================
# LIFECYCLE EVENTS
# ============================================================
@app.on_event("startup")
async def startup():
    ensure_api_keys_table()
    ensure_tenant_configs_table()

    detect_user_columns()
    detect_trades_columns()

    # This will now also create an approved device for admin
    ensure_admin_exists()

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

    if os.getenv("RUN_SELFTEST", "false").lower() == "true":
        try:
            passed = run_self_test_db()
            if passed:
                logger.info("✅ Self‑test PASSED – idempotency works (unique constraint enforced).")
            else:
                logger.error("⚠️ Self‑test FAILED – idempotency broken!")
        except Exception as e:
            logger.error(f"Self‑test error: {e}")

        asyncio.create_task(run_http_concurrency_test())

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
