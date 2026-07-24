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
    db = SyncSessionLocal()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"User {email} already exists.")
        return
    service = AuthService()
    hashed = service.hash_password(password)
    admin = User(
        email=email,
        hashed_password=hashed,
        full_name=full_name,
        status="approved",
        role="admin",
        tenant="default"
    )
    db.add(admin)
    db.commit()
    print(f"Admin user created: {email}")

if __name__ == "__main__":
    import getpass
    email = input("Admin email: ")
    password = getpass.getpass("Admin password: ")
    create_admin(email, password)
