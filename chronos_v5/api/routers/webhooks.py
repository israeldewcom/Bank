# chronos_v5/api/routers/webhooks.py
from fastapi import APIRouter, Depends, HTTPException, Query
from chronos_v5.api.dependencies import get_admin_user
from chronos_v5.models import User, Webhook
from chronos_v5.database import SyncSessionLocal
from chronos_v5.logger_setup import logger
from datetime import datetime, timezone
import uuid
import requests
import json
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

class WebhookCreate(BaseModel):
    name: str
    url: str
    events: List[str]
    secret: Optional[str] = None

class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    events: Optional[List[str]] = None
    status: Optional[str] = None
    secret: Optional[str] = None

@router.get("/")
def list_webhooks(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_admin_user)
):
    db = SyncSessionLocal()
    try:
        webhooks = db.query(Webhook).filter(
            Webhook.tenant == admin.tenant
        ).order_by(Webhook.created_at.desc()).limit(limit).offset(offset).all()
        return [
            {
                "id": w.id,
                "name": w.name,
                "url": w.url,
                "events": w.events,
                "status": w.status,
                "last_triggered": w.last_triggered.isoformat() if w.last_triggered else None,
            }
            for w in webhooks
        ]
    finally:
        db.close()

@router.post("/")
def create_webhook(data: WebhookCreate, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        webhook = Webhook(
            id=str(uuid.uuid4()),
            name=data.name,
            url=data.url,
            events=data.events,
            secret=data.secret,
            tenant=admin.tenant,
            status='active',
            created_at=datetime.now(timezone.utc)
        )
        db.add(webhook)
        db.commit()
        db.refresh(webhook)
        return {"id": webhook.id, "status": "created"}
    finally:
        db.close()

@router.post("/{webhook_id}/test")
def test_webhook(webhook_id: str, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        webhook = db.query(Webhook).filter(
            Webhook.id == webhook_id,
            Webhook.tenant == admin.tenant
        ).first()
        if not webhook:
            raise HTTPException(404, "Webhook not found")
        payload = {"event": "test", "timestamp": datetime.now(timezone.utc).isoformat()}
        headers = {"Content-Type": "application/json"}
        if webhook.secret:
            import hmac, hashlib
            signature = hmac.new(
                webhook.secret.encode(),
                json.dumps(payload).encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = signature
        try:
            resp = requests.post(webhook.url, json=payload, headers=headers, timeout=5)
            resp.raise_for_status()
            return {"status": "test_success", "response_code": resp.status_code}
        except Exception as e:
            return {"status": "test_failed", "error": str(e)}
    finally:
        db.close()

@router.delete("/{webhook_id}")
def delete_webhook(webhook_id: str, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        webhook = db.query(Webhook).filter(
            Webhook.id == webhook_id,
            Webhook.tenant == admin.tenant
        ).first()
        if not webhook:
            raise HTTPException(404, "Webhook not found")
        db.delete(webhook)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()
