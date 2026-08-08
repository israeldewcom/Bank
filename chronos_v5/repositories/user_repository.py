# chronos_v5/repositories/user_repository.py (enhanced with full CRUD)
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User
from chronos_v5.logger_setup import logger
import uuid
from datetime import datetime, timezone

class UserRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_by_email(self, email):
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id):
        return self.db.query(User).filter(User.id == str(user_id)).first()

    def get_all(self, tenant=None, limit=100, offset=0):
        query = self.db.query(User)
        if tenant:
            query = query.filter(User.tenant == tenant)
        return query.order_by(User.created_at.desc()).limit(limit).offset(offset).all()

    def get_pending(self, tenant=None):
        query = self.db.query(User).filter(User.status == 'pending')
        if tenant:
            query = query.filter(User.tenant == tenant)
        return query.all()

    def create(self, email, password_hash, full_name, tenant, role='user', status='pending', is_active=False):
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            tenant=tenant,
            role=role,
            status=status,
            is_active=is_active,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user_id, data):
        user = self.get_by_id(user_id)
        if not user:
            return None
        for key, value in data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user_id):
        user = self.get_by_id(user_id)
        if not user:
            return False
        self.db.delete(user)
        self.db.commit()
        return True

    def close(self):
        self.db.close()
