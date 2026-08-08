# chronos_v5/services/user_service.py
from chronos_v5.repositories.user_repository import UserRepository
from chronos_v5.services.auth_service import AuthService
from chronos_v5.logger_setup import logger
import bcrypt

class UserService:
    def __init__(self):
        self.repo = UserRepository()
        self.auth = AuthService()

    def get_all_users(self, tenant=None, limit=100, offset=0):
        return self.repo.get_all(tenant, limit, offset)

    def get_user(self, user_id):
        return self.repo.get_by_id(user_id)

    def create_user(self, email, password, full_name, tenant, role='user'):
        existing = self.repo.get_by_email(email)
        if existing:
            raise ValueError("Email already registered")
        hashed = self.auth.hash_password(password)
        user = self.repo.create(email, hashed, full_name, tenant, role)
        return user

    def update_user(self, user_id, data):
        if 'password' in data and data['password']:
            data['password_hash'] = self.auth.hash_password(data['password'])
            del data['password']
        user = self.repo.update(user_id, data)
        if not user:
            raise ValueError("User not found")
        return user

    def delete_user(self, user_id):
        if not self.repo.delete(user_id):
            raise ValueError("User not found")

    def approve_user(self, user_id):
        return self.repo.update(user_id, {'status': 'approved', 'is_active': True})

    def reject_user(self, user_id):
        return self.repo.update(user_id, {'status': 'rejected', 'is_active': False})

    def close(self):
        self.repo.close()
