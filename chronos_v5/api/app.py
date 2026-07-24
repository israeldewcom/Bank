# chronos_v5/api/app.py
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi_limiter import FastAPILimiter
import redis, asyncio, os
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

# --- EXISTING ROUTERS ---
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

# --- NEW AUTH/TENANT ROUTERS ---
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

@app.on_event("startup")
async def startup():
    # Conditionally initialize rate limiter only if not in test environment
    if Config.ENV != "test":
        redis_conn = redis.from_url(Config.REDIS_URL)
        await FastAPILimiter.init(redis_conn)
        logger.info("FastAPI-Limiter initialized")
    else:
        logger.info("Rate limiter disabled in test environment")

    if Config.ASYNC_DB:
        from chronos_v5.database import async_database
        if async_database:
            await async_database.connect()
            logger.info("Async DB connected")
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
