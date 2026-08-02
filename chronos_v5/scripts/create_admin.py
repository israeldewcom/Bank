# chronos_v5/scripts/create_admin.py
"""
Run this once to bootstrap the first admin user.
Usage: python -m chronos_v5.scripts.create_admin
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User
from chronos_v5.services.auth_service import AuthService
from chronos_v5.config import Config

def create_admin(email, password, full_name="Admin"):
    # BUG FIX: this constructed User(..., hashed_password=..., status="approved")
    # with no id and no is_active. models.py's User column is password_hash,
    # not hashed_password — the original call would raise
    # `TypeError: 'hashed_password' is an invalid keyword argument for User`
    # immediately. status="approved" is valid now that User.status exists,
    # but without is_active=True the resulting admin still couldn't pass
    # auth_service.validate_api_key()'s / login()'s is_active check. id is
    # left to the column default (str(uuid.uuid4())) rather than omitted,
    # since User.id has no server-side default at the DB level — only the
    # Python-side `default=` on the Column, which only applies when the
    # attribute is left unset (as it is here), so this is fine as written.
    db = SyncSessionLocal()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"User {email} already exists.")
        db.close()
        return
    service = AuthService()
    hashed = service.hash_password(password)
    admin = User(
        email=email,
        password_hash=hashed,
        full_name=full_name,
        status="approved",
        is_active=True,
        role="admin",
        tenant="default"
    )
    db.add(admin)
    db.commit()
    db.close()
    print(f"Admin user created: {email}")

if __name__ == "__main__":
    import getpass
    email = input("Admin email: ")
    password = getpass.getpass("Admin password: ")
    create_admin(email, password)
