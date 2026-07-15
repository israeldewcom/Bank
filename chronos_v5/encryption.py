from cryptography.fernet import Fernet
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

class EncryptionManager:
    def __init__(self):
        self.key = Config.ENCRYPTION_KEY.encode()
        self.cipher = Fernet(self.key)

    def encrypt(self, data: str) -> str:
        if not data:
            return data
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, token: str) -> str:
        if not token:
            return token
        return self.cipher.decrypt(token.encode()).decode()

    def encrypt_dict(self, data: dict, fields: list) -> dict:
        for field in fields:
            if field in data and data[field]:
                data[field] = self.encrypt(data[field])
        return data

encryption = EncryptionManager()
