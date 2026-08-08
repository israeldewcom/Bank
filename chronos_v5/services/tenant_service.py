# chronos_v5/services/tenant_service.py
from chronos_v5.repositories.tenant_repository import TenantRepository
from chronos_v5.logger_setup import logger

class TenantService:
    def __init__(self):
        self.repo = TenantRepository()

    def get_all_tenants(self, limit=100, offset=0):
        return self.repo.get_all(limit, offset)

    def get_tenant(self, tenant_id):
        return self.repo.get_by_id(tenant_id)

    def create_tenant(self, name, config=None):
        existing = self.repo.get_by_name(name)
        if existing:
            raise ValueError(f"Tenant '{name}' already exists")
        return self.repo.create(name, config)

    def update_tenant(self, tenant_id, data):
        tenant = self.repo.update(tenant_id, data)
        if not tenant:
            raise ValueError("Tenant not found")
        return tenant

    def delete_tenant(self, tenant_id):
        if not self.repo.delete(tenant_id):
            raise ValueError("Tenant not found")

    def close(self):
        self.repo.close()
