# chronos_v5/utils/jwt_utils.py
import jwt
from datetime import datetime, timedelta, timezone
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

def create_jwt(user_id: str, tenant: str, role: str, expires_delta: timedelta = None):
    if expires_delta is None:
        expires_delta = timedelta(minutes=Config.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "tenant": tenant,
        "role": role,
        "exp": datetime.now(timezone.utc) + expires_delta,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")

def decode_jwt(token: str):
    try:
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT: {e}")
        return None
