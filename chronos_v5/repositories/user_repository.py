# chronos_v5/repositories/user_repository.py
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User
import uuid

class UserRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_by_email(self, email: str):
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id):
        # BUG FIX: User.id is String(36) (see models.py), but this accepted
        # a uuid.UUID and filtered directly with it — comparing a UUID
        # object against a VARCHAR column, the same mismatch fixed in
        # api/routers/admin.py. Now normalizes to the canonical string form
        # regardless of whether the caller passes a str or a uuid.UUID.
        return self.db.query(User).filter(User.id == str(user_id)).first()

    def get_pending_users(self):
        # BUG FIX: User.status previously didn't exist on the ORM model at
        # all (see models.py) — this raised AttributeError on every call.
        # It's now a real column, and this correctly returns only
        # newly-registered, not-yet-reviewed accounts.
        return self.db.query(User).filter(User.status == "pending").all()
