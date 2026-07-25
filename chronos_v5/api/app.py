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
from chronos_v5.models import User, APIKey, Base
from sqlalchemy import text, inspect

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
# DYNAMIC COLUMN DETECTION
# ============================================================
def get_password_column():
    """Detect the actual column name for the password field in the User model."""
    inspector = inspect(User)
    columns = [c.name for c in inspector.columns]
    for col in ["password_hash", "hashed_password", "password", "pw_hash"]:
        if col in columns:
            return col
    # Fallback: return the first column that contains 'password'
    for col in columns:
        if "password" in col.lower():
            return col
    raise RuntimeError("Could not find a password column in the User model")

PASSWORD_COLUMN = None

# ============================================================
# ADMIN CREATION ON STARTUP (with dynamic column)
# ============================================================
def ensure_admin_exists():
    global PASSWORD_COLUMN
    if PASSWORD_COLUMN is None:
        try:
            PASSWORD_COLUMN = get_password_column()
            logger.info(f"Detected password column: {PASSWORD_COLUMN}")
        except Exception as e:
            logger.error(f"Failed to detect password column: {e}")
            return

    db = SyncSessionLocal()
    try:
        # Check for existing admin using the detected column
        admin_exists = db.query(User).filter(User.role == "admin").first()
        if admin_exists:
            logger.info("Admin user already exists – skipping creation.")
            return

        admin_email = os.getenv("ADMIN_EMAIL", "admin@chronos.local")
        admin_password = os.getenv("ADMIN_PASSWORD", "Admin123!")

        # Hash password
        hashed = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()

        # Create admin user with dynamic column
        admin_kwargs = {
            "id": uuid.uuid4(),
            "email": admin_email,
            "full_name": "System Admin",
            "status": "approved",
            "role": "admin",
            "tenant": "default",
            "created_at": datetime.now(timezone.utc)
        }
        admin_kwargs[PASSWORD_COLUMN] = hashed

        admin = User(**admin_kwargs)
        db.add(admin)
        db.commit()
        logger.info(f"✅ Admin user created with email: {admin_email}")

        # Generate API key
        raw_key = secrets.token_urlsafe(32)
        api_key = APIKey(
            user_id=admin.id,
            key_prefix=raw_key[:12],
            key_hash=bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode(),
            tenant="default"
        )
        db.add(api_key)
        db.commit()
        logger.info(f"🔑 Admin API key (copy this): {raw_key}")
    except Exception as e:
        logger.error(f"Failed to create admin: {e}")
    finally:
        db.close()

# ============================================================
# SELF‑TEST FUNCTION (with dynamic column)
# ============================================================
async def run_self_test():
    global PASSWORD_COLUMN
    if PASSWORD_COLUMN is None:
        try:
            PASSWORD_COLUMN = get_password_column()
        except Exception as e:
            logger.error(f"Cannot run self‑test: {e}")
            return False

    base_url = f"http://localhost:{os.getenv('PORT', '10000')}"
    db = SyncSessionLocal()

    try:
        test_email = f"self_test_{uuid.uuid4().hex[:8]}@chronos.local"
        test_user_kwargs = {
            "id": uuid.uuid4(),
            "email": test_email,
            "full_name": "Self Test",
            "status": "approved",
            "role": "user",
            "tenant": "default",
            "created_at": datetime.now(timezone.utc)
        }
        test_user_kwargs[PASSWORD_COLUMN] = bcrypt.hashpw(b"temp_pass", bcrypt.gensalt()).decode()

        test_user = User(**test_user_kwargs)
        db.add(test_user)
        db.commit()

        raw_key = secrets.token_urlsafe(32)
        api_key = APIKey(
            user_id=test_user.id,
            key_prefix=raw_key[:12],
            key_hash=bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode(),
            tenant="default"
        )
        db.add(api_key)
        db.commit()
        db.close()
    except Exception as e:
        db.close()
        logger.error(f"Self‑test DB setup failed: {e}")
        return False

    logger.info(f"Self‑test: created temporary user {test_email} with API key")

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
    # --- Admin creation (synchronous) ---
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
