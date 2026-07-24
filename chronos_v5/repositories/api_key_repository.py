# chronos_v5/repositories/api_key_repository.py
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import APIKey
import uuid

class APIKeyRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_active_keys(self, tenant: str):
        return self.db.query(APIKey).filter(
            APIKey.tenant == tenant,
            APIKey.revoked_at.is_(None)
        ).all()
