# chronos_v5/services/device_service.py
from chronos_v5.repositories.device_repository import DeviceRepository
from chronos_v5.logger_setup import logger
from datetime import datetime, timezone

class DeviceService:
    def __init__(self):
        self.repo = DeviceRepository()

    def get_all_devices(self, tenant=None, limit=100, offset=0):
        return self.repo.get_all(tenant, limit, offset)

    def get_device(self, device_id):
        return self.repo.get_by_id(device_id)

    def create_device(self, user_id, device_name, fingerprint, tenant):
        return self.repo.create(user_id, device_name, fingerprint, tenant)

    def approve_device(self, device_id, admin_id):
        return self.repo.update(device_id, {
            'status': 'approved',
            'approved_by': str(admin_id),
            'approved_at': datetime.now(timezone.utc)
        })

    def revoke_device(self, device_id):
        return self.repo.update(device_id, {'status': 'revoked'})

    def delete_device(self, device_id):
        if not self.repo.delete(device_id):
            raise ValueError("Device not found")

    def close(self):
        self.repo.close()
