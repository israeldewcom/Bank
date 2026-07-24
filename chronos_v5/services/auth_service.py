# chronos_v5/services/auth_service.py
import bcrypt
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User, APIKey, Device, PairingCode
from chronos_v5.utils.jwt_utils import create_jwt
from chronos_v5.logger_setup import logger
from chronos_v5.config import Config

class AuthService:
    def __init__(self):
        self.db = SyncSessionLocal()

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def verify_password(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    def register_user(self, email: str, password: str, full_name: str, tenant: str = "default"):
        if self.db.query(User).filter(User.email == email).first():
            raise ValueError("Email already registered")
        user = User(
            email=email,
            hashed_password=self.hash_password(password),
            full_name=full_name,
            status="pending",
            role="user",
            tenant=tenant
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"User registered: {email} (tenant: {tenant})")
        return user

    def approve_user(self, user_id: uuid.UUID, admin_id: uuid.UUID):
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        if user.status != "pending":
            raise ValueError("User is not pending")
        user.status = "approved"
        user.approved_by = admin_id
        user.approved_at = datetime.now(timezone.utc)
        # Generate API key automatically
        raw_key = self.generate_api_key(user.id)
        self.db.commit()
        logger.info(f"User {user.email} approved by admin {admin_id}")
        return raw_key

    def reject_user(self, user_id: uuid.UUID):
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        user.status = "rejected"
        self.db.commit()
        logger.info(f"User {user.email} rejected")

    def generate_api_key(self, user_id: uuid.UUID) -> str:
        raw = secrets.token_urlsafe(32)  # 43 characters
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
        # We can't search by raw, so we need to iterate (or store a hash prefix)
        # For performance, we store a hash of the full key.
        # We'll retrieve all active keys for the tenant and check bcrypt.
        # In production, add a lookup by key_prefix first.
        all_keys = self.db.query(APIKey).filter(APIKey.revoked_at.is_(None)).all()
        for key in all_keys:
            if bcrypt.checkpw(raw_key.encode(), key.key_hash.encode()):
                user = self.db.query(User).filter(User.id == key.user_id).first()
                if user and user.status == "approved":
                    key.last_used_at = datetime.now(timezone.utc)
                    self.db.commit()
                    return user, key
        return None, None

    def create_pairing_code(self, user_id: uuid.UUID, device_name: str) -> str:
        # Generate 6-digit numeric code
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

    def approve_device(self, device_id: uuid.UUID, admin_id: uuid.UUID):
        device = self.db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise ValueError("Device not found")
        device.status = "approved"
        device.approved_by = admin_id
        device.approved_at = datetime.now(timezone.utc)
        self.db.commit()
        return device

    def login(self, email: str, password: str, device_fingerprint: str = None):
        user = self.db.query(User).filter(User.email == email).first()
        if not user or not self.verify_password(password, user.hashed_password):
            raise ValueError("Invalid credentials")
        if user.status != "approved":
            raise ValueError("User account not approved")
        # Optionally validate device if fingerprint provided
        if device_fingerprint:
            device = self.db.query(Device).filter(
                Device.user_id == user.id,
                Device.device_fingerprint == device_fingerprint,
                Device.status == "approved"
            ).first()
            if not device:
                raise ValueError("Device not approved")
            device.last_used_at = datetime.now(timezone.utc)
            self.db.commit()
        token = create_jwt(str(user.id), user.tenant, user.role)
        return token
