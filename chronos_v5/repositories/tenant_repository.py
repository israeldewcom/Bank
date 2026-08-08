# chronos_v5/repositories/tenant_repository.py
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Tenant
from chronos_v5.logger_setup import logger
import uuid
from datetime import datetime, timezone

class TenantRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_all(self, limit=100, offset=0):
        return self.db.query(Tenant).order_by(Tenant.created_at.desc()).limit(limit).offset(offset).all()

    def get_by_id(self, tenant_id):
        return self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def get_by_name(self, name):
        return self.db.query(Tenant).filter(Tenant.name == name).first()

    def create(self, name, config=None):
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=name,
            status='pending',
            config=config or {},
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def update(self, tenant_id, data):
        tenant = self.get_by_id(tenant_id)
        if not tenant:
            return None
        for key, value in data.items():
            if hasattr(tenant, key):
                setattr(tenant, key, value)
        tenant.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def delete(self, tenant_id):
        tenant = self.get_by_id(tenant_id)
        if not tenant:
            return False
        self.db.delete(tenant)
        self.db.commit()
        return True

    def close(self):
        self.db.close()
