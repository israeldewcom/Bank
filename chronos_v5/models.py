# chronos_v5/models.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime,
    Text, BigInteger, ForeignKey, Index, JSON, Enum as SQLAEnum
)
from datetime import datetime, timezone
import uuid
from sqlalchemy.dialects.postgresql import UUID

Base = declarative_base()

# === EXISTING TABLES (unchanged) ===
class Trade(Base):
    __tablename__ = "trades"
    id = Column(String(36), primary_key=True)
    desk = Column(String(100), nullable=False)
    counterparty_id = Column(String(100), nullable=False)
    instrument_type = Column(String(50))
    currency = Column(String(10), nullable=False)
    notional = Column(Float, nullable=False)
    settle_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(20), default="PENDING")
    fail_probability = Column(Float, default=0.0)
    price_quote = Column(JSON, nullable=True)
    idempotency_key = Column(String(100), unique=True, nullable=True)
    encrypted_counterparty = Column(Text, nullable=True)
    tenant = Column(String(50), default="default", nullable=False, index=True)  # NEW

class Counterparty(Base):
    __tablename__ = "counterparties"
    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    risk_score = Column(Float, default=0.1)
    credit_rating = Column(String(10))
    total_exposure = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class FailHistory(Base):
    __tablename__ = "fail_history"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_id = Column(String(36), nullable=False)
    failed = Column(Boolean, nullable=False)
    failure_reason = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notional = Column(Float)

class PnLAttribution(Base):
    __tablename__ = "pnl_attribution"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_id = Column(String(36), nullable=False)
    strategy = Column(String(50))
    amount_saved = Column(Float, nullable=False)
    currency = Column(String(10), default="NGN")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    metadata_json = Column(Text, nullable=True)
    tenant = Column(String(50), default="default", nullable=False, index=True)  # NEW

class CollateralHolding(Base):
    __tablename__ = "collateral_holdings"
    id = Column(BigInteger, primary_key=True)
    counterparty_id = Column(String(100), nullable=False)
    asset_type = Column(String(50), nullable=False)
    quantity = Column(Float, nullable=False)
    market_value = Column(Float, nullable=False)
    haircut = Column(Float, nullable=False)
    eligible = Column(Boolean, default=True)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class MarketDataPoint(Base):
    __tablename__ = "market_data"
    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(50), nullable=False)
    price = Column(Float, nullable=False)
    volume = Column(Float)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    source = Column(String(50))

class AlphaSignal(Base):
    __tablename__ = "alpha_signals"
    id = Column(BigInteger, primary_key=True)
    asset = Column(String(50), nullable=False)
    signal_value = Column(Float, nullable=False)
    strategy = Column(String(50))
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expiry = Column(DateTime)

class ExecutionOrder(Base):
    __tablename__ = "execution_orders"
    id = Column(BigInteger, primary_key=True)
    trade_id = Column(String(36), nullable=False, index=True)
    order_type = Column(String(20))
    side = Column(String(10))
    quantity = Column(Float)
    price = Column(Float)
    status = Column(String(20))
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    filled_at = Column(DateTime)
    external_order_id = Column(String(100))

class RiskMetrics(Base):
    __tablename__ = "risk_metrics"
    id = Column(BigInteger, primary_key=True)
    desk = Column(String(100), nullable=False)
    var_99 = Column(Float)
    expected_shortfall = Column(Float)
    stress_loss = Column(Float)
    capital_usage = Column(Float)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# === NEW TABLES (AUTH + TENANT CONFIG) ===

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    status = Column(SQLAEnum("pending", "approved", "rejected", "suspended", name="user_status"), default="pending")
    role = Column(SQLAEnum("user", "developer", "admin", name="user_role"), default="user")
    tenant = Column(String(50), default="default", nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

class APIKey(Base):
    __tablename__ = "api_keys"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key_prefix = Column(String(20), nullable=False)
    key_hash = Column(String(255), nullable=False)
    tenant = Column(String(50), default="default", nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)

class Device(Base):
    __tablename__ = "devices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    device_name = Column(String(255))
    device_fingerprint = Column(String(255), nullable=False)  # <-- now NOT NULL
    status = Column(SQLAEnum("pending", "approved", "revoked", name="device_status"), default="pending")
    tenant = Column(String(50), default="default", nullable=False, index=True)
    requested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)

class PairingCode(Base):
    __tablename__ = "pairing_codes"
    code = Column(String(10), primary_key=True)  # 6‑digit, short‑lived
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    device_name = Column(String(255))
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, default=False)

class TenantConfig(Base):
    __tablename__ = "tenant_configs"
    tenant = Column(String(50), primary_key=True)
    performance_fee_percent = Column(Float, default=0.20)
    bloomberg_api_key_enc = Column(Text, nullable=True)
    reuters_api_key_enc = Column(Text, nullable=True)
    alpha_vantage_key_enc = Column(Text, nullable=True)
    nibss_api_key_enc = Column(Text, nullable=True)
    cbn_openapi_url = Column(String(255), nullable=True)
    ngx_api_url = Column(String(255), nullable=True)
    use_global_model = Column(Boolean, default=True)
    alpha_strategy_type = Column(String(50), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
