# chronos_v5/api/routers/backup.py
from fastapi import APIRouter, Depends, HTTPException, Query
from chronos_v5.api.dependencies import get_admin_user
from chronos_v5.models import User, BackupRecord
from chronos_v5.database import SyncSessionLocal
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
import os
import subprocess
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/admin/backups", tags=["Backup"])

@router.get("/")
def list_backups(
    limit: int = Query(50, ge=1, le=100),
    admin: User = Depends(get_admin_user)
):
    db = SyncSessionLocal()
    try:
        records = db.query(BackupRecord).filter(
            BackupRecord.tenant == admin.tenant
        ).order_by(BackupRecord.started_at.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "file_path": r.file_path,
                "size_bytes": r.size_bytes,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "error_message": r.error_message,
            }
            for r in records
        ]
    finally:
        db.close()

@router.post("/")
def create_backup(admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        record = BackupRecord(
            id=str(uuid.uuid4()),
            file_path="",
            status="pending",
            tenant=admin.tenant,
            started_at=datetime.now(timezone.utc)
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        from chronos_v5.tasks import create_database_backup
        create_database_backup.delay(record.id, admin.tenant)

        return {"status": "backup_initiated", "id": record.id}
    finally:
        db.close()

@router.post("/{backup_id}/restore")
def restore_backup(backup_id: str, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        record = db.query(BackupRecord).filter(
            BackupRecord.id == backup_id,
            BackupRecord.tenant == admin.tenant
        ).first()
        if not record:
            raise HTTPException(404, "Backup record not found")
        if record.status != 'completed':
            raise HTTPException(400, "Backup not completed or failed")
        from chronos_v5.tasks import restore_database_backup
        restore_database_backup.delay(record.file_path, admin.tenant)
        return {"status": "restore_initiated", "backup_id": backup_id}
    finally:
        db.close()
