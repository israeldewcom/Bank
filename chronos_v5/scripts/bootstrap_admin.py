#!/usr/bin/env python3
import os
import sys
import uuid
import bcrypt
import secrets
import base64
import argparse
from datetime import datetime, timezone
from getpass import getpass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chronos_v5.config import Config
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User, APIKey
from chronos_v5.logger_setup import logger

WEAK_PASSWORDS = {"Admin123!", "password", "admin", "changeme", "123456"}

def is_weak_password(pw: str) -> bool:
    return pw in WEAK_PASSWORDS or len(pw) < 8

def create_k8s_secret(secret_name: str, namespace: str, key_value: str) -> bool:
    try:
        from kubernetes import client, config
        config.load_incluster_config()
        v1 = client.CoreV1Api()
        try:
            existing = v1.read_namespaced_secret(name=secret_name, namespace=namespace)
            logger.error(f"Secret {secret_name} already exists in namespace {namespace}. Refusing to overwrite.")
            return False
        except client.exceptions.ApiException as e:
            if e.status != 404:
                logger.error(f"Unexpected error checking secret: {e}")
                return False
        secret = client.V1Secret(
            metadata=client.V1ObjectMeta(name=secret_name, namespace=namespace),
            data={"admin-api-key": base64.b64encode(key_value.encode()).decode()}
        )
        v1.create_namespaced_secret(namespace=namespace, body=secret)
        logger.info(f"✅ API key stored in Kubernetes Secret {secret_name} in namespace {namespace}")
        return True
    except ImportError:
        logger.warning("kubernetes Python client not installed; falling back to file storage.")
        return False
    except Exception as e:
        logger.error(f"Failed to create Kubernetes Secret: {e}")
        return False

def _ensure_admin_device(db, admin_id):
    """Create an approved device for the admin if missing."""
    try:
        from sqlalchemy import text
        result = db.execute(
            text("SELECT id FROM devices WHERE user_id = :uid AND device_fingerprint = 'web-client'"),
            {"uid": admin_id}
        )
        if not result.fetchone():
            db.execute(
                text("""
                    INSERT INTO devices (id, user_id, device_name, device_fingerprint, status, tenant, requested_at, approved_at)
                    VALUES (gen_random_uuid(), :uid, 'Default Web Client', 'web-client', 'approved', 'default', NOW(), NOW())
                """),
                {"uid": admin_id}
            )
            db.commit()
            logger.info(f"✅ Approved device 'web-client' created for admin {admin_id}")
    except Exception as e:
        logger.error(f"Failed to ensure admin device: {e}")
        db.rollback()

def bootstrap_admin(output_file: str = None):
    env = Config.ENV
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if env == "production":
        if not admin_email or not admin_password:
            logger.error("ADMIN_EMAIL and ADMIN_PASSWORD must be set in production.")
            sys.exit(1)
        if is_weak_password(admin_password):
            logger.error("ADMIN_PASSWORD is too weak. Use a strong password.")
            sys.exit(1)
    else:
        if not admin_email:
            admin_email = input("Admin email: ").strip()
        if not admin_password:
            admin_password = getpass("Admin password: ").strip()
        if is_weak_password(admin_password):
            logger.warning("Password is weak; allowed in non-production environment.")

    db = SyncSessionLocal()
    try:
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            logger.info(f"Admin user {admin_email} already exists. Skipping creation.")
            # Still ensure device exists
            _ensure_admin_device(db, existing.id)
            return

        hashed = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
        admin_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        admin = User(
            id=admin_id,
            email=admin_email,
            password_hash=hashed,
            full_name="System Admin",
            status="approved",
            is_active=True,
            role="admin",
            tenant="default",
            created_at=now,
        )
        db.add(admin)
        db.commit()

        # Create device immediately
        _ensure_admin_device(db, admin_id)

        raw_key = secrets.token_urlsafe(32)
        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
        api_key = APIKey(
            id=str(uuid.uuid4()),
            user_id=admin_id,
            key_prefix=raw_key[:12],
            key_hash=key_hash,
            tenant="default",
            created_at=now,
        )
        db.add(api_key)
        db.commit()

        stored = False
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            secret_name = os.getenv("K8S_SECRET_NAME", "chronos-admin-key")
            namespace = os.getenv("K8S_SECRET_NAMESPACE", "default")
            if create_k8s_secret(secret_name, namespace, raw_key):
                stored = True
                logger.info("API key stored in Kubernetes Secret. Retrieve with:")
                logger.info(f"  kubectl get secret {secret_name} -n {namespace} -o jsonpath='{{.data.admin-api-key}}' | base64 -d")
            else:
                logger.warning("Falling back to file output for API key.")

        if not stored and output_file:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            with open(output_file, "w") as f:
                f.write(raw_key)
            os.chmod(output_file, 0o600)
            logger.info(f"✅ API key written to {output_file}")
            stored = True

        if not stored:
            logger.critical("⚠️ No secure storage method succeeded. Printing API key to stdout.")
            print(f"API Key: {raw_key}")
            logger.critical("Capture this key immediately and store it securely.")

        logger.info(f"Admin user created: {admin_email}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to bootstrap admin: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-file", help="Path to write the API key (secure file).")
    args = parser.parse_args()
    bootstrap_admin(output_file=args.output_file)
