# chronos_v5/services/auth_service.py
import bcrypt
import secrets
import uuid
import re
from datetime import datetime, timedelta, timezone
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User, APIKey, Device, PairingCode
from chronos_v5.utils.jwt_utils import create_jwt
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
        if self.db.query(User).filter(User.email == email).first():
            raise ValueError("Email already registered")
        self.validate_password_policy(password)
        user = User(
            email=email,
            password_hash=self.hash_password(password),
            full_name=full_name,
            tenant=tenant,
            created_at=datetime.now(timezone.utc),
            is_active=True
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"User registered: {email} (tenant: {tenant})")
        return user

    def approve_user(self, user_id: str, admin_id: str):
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        user.is_active = True
        raw_key = self.generate_api_key(user.id)
        self.db.commit()
        logger.info(f"User {user.email} approved by admin {admin_id}")
        return raw_key

    def reject_user(self, user_id: str):
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        user.is_active = False
        self.db.commit()
        logger.info(f"User {user.email} rejected")

    def generate_api_key(self, user_id: str) -> str:
        raw = secrets.token_urlsafe(32)
        prefix = raw[:12]
        hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()
        key = APIKey(
            user_id=user_id,
            key_prefix=prefix,
            key_hash=hashed,
            tenant=self.db.query(User).filter(User.id == user_id).first().tenant
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
                    user = self.db.query(User).filter(User.id == key.user_id).first()
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
            user_id=user_id,
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
            user_id=pairing.user_id,
            device_name=pairing.device_name,
            device_fingerprint=device_fingerprint,
            status="pending",
            tenant=self.db.query(User).filter(User.id == pairing.user_id).first().tenant
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def approve_device(self, device_id: str, admin_id: str):
        device = self.db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise ValueError("Device not found")
        device.status = "approved"
        device.approved_by = admin_id
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
        self.db.commit()
        token = create_jwt(user.id, user.tenant, "user")  # no role column
        return token
