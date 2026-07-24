# chronos_v5/repositories/user_repository.py
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User
import uuid

class UserRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_by_email(self, email: str):
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: uuid.UUID):
        return self.db.query(User).filter(User.id == user_id).first()

    def get_pending_users(self):
        return self.db.query(User).filter(User.status == "pending").all()
