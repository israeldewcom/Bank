# chronos_v5/repositories/device_repository.py
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Device
import uuid

class DeviceRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_pending_devices(self, tenant: str):
        return self.db.query(Device).filter(
            Device.tenant == tenant,
            Device.status == "pending"
        ).all()
