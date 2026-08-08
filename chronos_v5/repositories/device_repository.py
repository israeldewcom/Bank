# chronos_v5/repositories/device_repository.py (enhanced)
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Device
from chronos_v5.logger_setup import logger
import uuid
from datetime import datetime, timezone

class DeviceRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_by_id(self, device_id):
        return self.db.query(Device).filter(Device.id == str(device_id)).first()

    def get_all(self, tenant=None, limit=100, offset=0):
        query = self.db.query(Device)
        if tenant:
            query = query.filter(Device.tenant == tenant)
        return query.order_by(Device.requested_at.desc()).limit(limit).offset(offset).all()

    def get_pending(self, tenant=None):
        query = self.db.query(Device).filter(Device.status == 'pending')
        if tenant:
            query = query.filter(Device.tenant == tenant)
        return query.all()

    def create(self, user_id, device_name, device_fingerprint, tenant, status='pending'):
        device = Device(
            id=str(uuid.uuid4()),
            user_id=str(user_id),
            device_name=device_name,
            device_fingerprint=device_fingerprint,
            tenant=tenant,
            status=status,
            requested_at=datetime.now(timezone.utc)
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def update(self, device_id, data):
        device = self.get_by_id(device_id)
        if not device:
            return None
        for key, value in data.items():
            if hasattr(device, key):
                setattr(device, key, value)
        self.db.commit()
        self.db.refresh(device)
        return device

    def delete(self, device_id):
        device = self.get_by_id(device_id)
        if not device:
            return False
        self.db.delete(device)
        self.db.commit()
        return True

    def close(self):
        self.db.close()
