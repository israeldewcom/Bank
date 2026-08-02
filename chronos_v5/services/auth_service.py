# chronos_v5/services/auth_service.py
import bcrypt
import secrets
import uuid
import re
import redis
from datetime import datetime, timedelta, timezone
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User, APIKey, Device, PairingCode
from chronos_v5.utils.jwt_utils import create_jwt, decode_jwt
from chronos_v5.logger_setup import logger
from chronos_v5.config import Config
from sqlalchemy import inspect

class AuthService:
    def __init__(self):
        self.db = SyncSessionLocal()

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def verify_password(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    def validate_password_policy(self, password: str) -> bool:
        if len(password) < Config.PASSWORD_MIN_LENGTH:
            raise ValueError(f"Password must be at least {Config.PASSWORD_MIN_LENGTH} characters")
        if Config.PASSWORD_REQUIRE_UPPER and not re.search(r'[A-Z]', password):
            raise ValueError("Password must contain at least one uppercase letter")
        if Config.PASSWORD_REQUIRE_LOWER and not re.search(r'[a-z]', password):
            raise ValueError("Password must contain at least one lowercase letter")
        if Config.PASSWORD_REQUIRE_DIGIT and not re.search(r'\d', password):
            raise ValueError("Password must contain at least one digit")
        if Config.PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValueError("Password must contain at least one special character")
        return True

    def register_user(self, email: str, password: str, full_name: str, tenant: str = "default"):
        # BUG FIX: this previously set is_active=True at registration while
        # the /auth/register endpoint told the caller "Awaiting admin
        # approval" — the message and the actual account state contradicted
        # each other, so a brand-new, unreviewed account could authenticate
        # immediately. New accounts now start status="pending",
        # is_active=False, and only become usable once an admin calls
        # approve_user() below.
        if self.db.query(User).filter(User.email == email).first():
            raise ValueError("Email already registered")
        self.validate_password_policy(password)
        user = User(
            email=email,
            password_hash=self.hash_password(password),
            full_name=full_name,
            tenant=tenant,
            created_at=datetime.now(timezone.utc),
            status="pending",
            is_active=False
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"User registered: {email} (tenant: {tenant}, status: pending)")
        return user

    def approve_user(self, user_id: str, admin_id: str):
        # Ensure user_id is string
        user = self.db.query(User).filter(User.id == str(user_id)).first()
        if not user:
            raise ValueError("User not found")
        user.status = "approved"
        user.is_active = True
        raw_key = self.generate_api_key(user.id)
        self.db.commit()
        logger.info(f"User {user.email} approved by admin {admin_id}")
        return raw_key

    def reject_user(self, user_id: str):
        user = self.db.query(User).filter(User.id == str(user_id)).first()
        if not user:
            raise ValueError("User not found")
        user.status = "rejected"
        user.is_active = False
        self.db.commit()
        logger.info(f"User {user.email} rejected")

    def generate_api_key(self, user_id: str) -> str:
        raw = secrets.token_urlsafe(32)
        prefix = raw[:12]
        hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()
        key = APIKey(
            user_id=str(user_id),  # ensure string
            key_prefix=prefix,
            key_hash=hashed,
            tenant=self.db.query(User).filter(User.id == str(user_id)).first().tenant
        )
        self.db.add(key)
        self.db.commit()
        return raw

    def validate_api_key(self, raw_key: str) -> tuple:
        prefix = raw_key[:12]
        try:
            candidates = self.db.query(APIKey).filter(
                APIKey.key_prefix == prefix,
                APIKey.revoked_at.is_(None)
            ).all()
            for key in candidates:
                if bcrypt.checkpw(raw_key.encode(), key.key_hash.encode()):
                    # Always convert to string for DB lookup
                    user = self.db.query(User).filter(User.id == str(key.user_id)).first()
                    if user and user.is_active:
                        return user, key
            return None, None
        except Exception as e:
            logger.error(f"validate_api_key error: {e}")
            self.db.rollback()
            return None, None

    def create_pairing_code(self, user_id: str, device_name: str) -> str:
        code = f"{secrets.randbelow(1000000):06d}"
        expires = datetime.now(timezone.utc) + timedelta(minutes=5)
        pairing = PairingCode(
            code=code,
            user_id=str(user_id),
            device_name=device_name,
            expires_at=expires
        )
        self.db.add(pairing)
        self.db.commit()
        return code

    def pair_device(self, code: str, device_fingerprint: str) -> Device:
        pairing = self.db.query(PairingCode).filter(
            PairingCode.code == code,
            PairingCode.consumed == False,
            PairingCode.expires_at > datetime.now(timezone.utc)
        ).first()
        if not pairing:
            raise ValueError("Invalid or expired pairing code")
        pairing.consumed = True
        device = Device(
            user_id=str(pairing.user_id),
            device_name=pairing.device_name,
            device_fingerprint=device_fingerprint,
            status="pending",
            tenant=self.db.query(User).filter(User.id == str(pairing.user_id)).first().tenant
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def approve_device(self, device_id: str, admin_id: str):
        device = self.db.query(Device).filter(Device.id == str(device_id)).first()
        if not device:
            raise ValueError("Device not found")
        device.status = "approved"
        device.approved_by = str(admin_id)
        device.approved_at = datetime.now(timezone.utc)
        self.db.commit()
        return device

    def login(self, email: str, password: str, device_fingerprint: str):
        if not device_fingerprint:
            raise ValueError("Device fingerprint is required")
        user = self.db.query(User).filter(User.email == email).first()
        if not user or not self.verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")
        if not user.is_active:
            raise ValueError("User account not active")
        device = self.db.query(Device).filter(
            Device.user_id == user.id,
            Device.device_fingerprint == device_fingerprint,
            Device.status == "approved"
        ).first()
        if not device:
            raise ValueError("Device not approved or does not exist")
        device.last_used_at = datetime.now(timezone.utc)
        user.last_login = datetime.now(timezone.utc)
        self.db.commit()
        # SECURITY FIX: JWTs previously had no jti and no revocation path —
        # a stolen or leaked token stayed valid for its full
        # JWT_EXPIRE_MINUTES (24h by default) with no way to invalidate it
        # server-side on logout, password change, or account compromise.
        # create_jwt now issues a jti and this service exposes
        # revoke_token()/is_token_revoked() backed by a short-lived Redis
        # blacklist keyed by jti (TTL'd to the token's own remaining life,
        # so the blacklist never outgrows the tokens it's protecting).
        jti = str(uuid.uuid4())
        token = create_jwt(user.id, user.tenant, user.role, jti=jti)
        return token

    def _redis(self):
        return redis.from_url(Config.REDIS_URL)

    def revoke_token(self, token: str) -> bool:
        """Blacklist a JWT by its jti until the token's own expiry."""
        payload = decode_jwt(token)
        if not payload:
            return False
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            return False
        ttl = max(int(exp - datetime.now(timezone.utc).timestamp()), 1)
        r = self._redis()
        r.setex(f"jwt:revoked:{jti}", ttl, "1")
        logger.info(f"Token revoked (jti={jti})")
        return True

    def is_token_revoked(self, jti: str) -> bool:
        if not jti:
            return False
        r = self._redis()
        return r.exists(f"jwt:revoked:{jti}") == 1

    def logout(self, token: str) -> bool:
        return self.revoke_token(token)
