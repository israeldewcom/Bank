from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime,
    Text, BigInteger, ForeignKey, Index, JSON
)
from datetime import datetime, timezone
import bcrypt

Base = declarative_base()

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

# ===== NEW USER MODEL =====
class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    tenant = Column(String(100), nullable=False, default="default")
    role = Column(String(50), default="user")  # "admin" or "user"
    is_active = Column(Boolean, default=True)
    trial_expiry = Column(DateTime, nullable=True)  # Null means unlimited / paid
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)

    def set_password(self, password: str):
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())
