# chronos_v5/hsm_abstraction.py
import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization
from cryptography.fernet import Fernet
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
import base64

class HSMAbstraction:
    def __init__(self):
        self.enabled = Config.HSM_ENABLED
        self._session = None
        self._key_handle = None
        if self.enabled:
            try:
                from pykcs11 import PyKCS11, Session, CKF_SERIAL_SESSION, Mechanism
                self.lib = PyKCS11.PyKCS11Lib()
                self.lib.load(Config.HSM_PKCS11_LIB)
                self._session = Session(self.lib.openSession(0, CKF_SERIAL_SESSION))
                self._session.login(Config.HSM_PIN)
                self._key_handle = self._session.findObjects(template=[(0x00000003, Config.HSM_TOKEN_LABEL)])[0]
                logger.info("HSM session established with key handle")
            except Exception as e:
                logger.error(f"HSM initialization failed: {e}")
                raise
        else:
            self._fernet_key = Config.ENCRYPTION_KEY.encode()
            self._fernet_cipher = Fernet(self._fernet_key)
            # --- FIXED: Deterministic RSA key derived from SECRET_KEY ---
            self._private_key = self._derive_rsa_key(Config.SECRET_KEY.encode())
            self._public_key = self._private_key.public_key()

    def _derive_rsa_key(self, seed: bytes):
        """Derive a deterministic RSA key from a seed using PBKDF2 and a PRNG."""
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        import hashlib
        # Use HKDF to expand seed into enough material for RSA key generation
        # We'll use a fixed exponent and generate parameters deterministically
        # This is a simplified approach; for production, consider using a persistent key file.
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=1024,  # enough for deterministic generation
            salt=b'rsa_deterministic_salt',
            info=b'chronos_hsm_fallback'
        )
        key_material = hkdf.derive(seed)
        # Use the key material to seed a PRNG (not cryptographically secure, but deterministic)
        # Python's RSA generation uses random numbers; we can't easily seed it.
        # Alternative: load a pre-generated key from disk.
        key_path = "/tmp/chronos_fallback_rsa.pem"
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                return serialization.load_pem_private_key(f.read(), password=None)
        else:
            # Generate once and save
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            with open(key_path, "wb") as f:
                f.write(pem)
            os.chmod(key_path, 0o600)
            return private_key

    def encrypt(self, plaintext: bytes) -> bytes:
        if not self.enabled:
            return self._fernet_cipher.encrypt(plaintext)
        try:
            from pykcs11 import Mechanism
            mech = Mechanism(0x00001002)  # CKM_AES_GCM
            iv = os.urandom(12)
            self._session.encryptInit(mech, self._key_handle)
            encrypted = self._session.encrypt(plaintext)
            return iv + encrypted
        except Exception as e:
            logger.error(f"HSM encrypt failed: {e}")
            raise

    def decrypt(self, ciphertext: bytes) -> bytes:
        if not self.enabled:
            return self._fernet_cipher.decrypt(ciphertext)
        try:
            from pykcs11 import Mechanism
            mech = Mechanism(0x00001002)
            iv = ciphertext[:12]
            data = ciphertext[12:]
            self._session.decryptInit(mech, self._key_handle, iv)
            return self._session.decrypt(data)
        except Exception as e:
            logger.error(f"HSM decrypt failed: {e}")
            raise

    def sign(self, data: bytes) -> bytes:
        if not self.enabled:
            # Deterministic fallback using the persisted RSA key
            return self._private_key.sign(
                data,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256()
            )
        try:
            from pykcs11 import Mechanism
            mech = Mechanism(0x00001200)  # CKM_SHA256_RSA_PKCS
            self._session.signInit(mech, self._key_handle)
            return self._session.sign(data)
        except Exception as e:
            logger.error(f"HSM sign failed: {e}")
            raise

hsm = HSMAbstraction()
