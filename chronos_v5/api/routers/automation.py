# chronos_v5/api/routers/automation.py
from fastapi import APIRouter, Depends, HTTPException, Query
from chronos_v5.api.dependencies import get_admin_user
from chronos_v5.models import User, AutomationJob
from chronos_v5.database import SyncSessionLocal
from chronos_v5.logger_setup import logger
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/automation/jobs", tags=["Automation"])

class JobCreate(BaseModel):
    name: str
    description: Optional[str] = None
    schedule: str
    job_type: str
    payload: Optional[dict] = None

class JobUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    schedule: Optional[str] = None
    status: Optional[str] = None
    payload: Optional[dict] = None

@router.get("/")
def list_jobs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_admin_user)
):
    db = SyncSessionLocal()
    try:
        jobs = db.query(AutomationJob).filter(
            AutomationJob.tenant == admin.tenant
        ).order_by(AutomationJob.created_at.desc()).limit(limit).offset(offset).all()
        return [
            {
                "id": j.id,
                "name": j.name,
                "description": j.description,
                "schedule": j.schedule,
                "job_type": j.job_type,
                "status": j.status,
                "last_run": j.last_run.isoformat() if j.last_run else None,
                "next_run": j.next_run.isoformat() if j.next_run else None,
            }
            for j in jobs
        ]
    finally:
        db.close()

@router.post("/")
def create_job(data: JobCreate, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        job = AutomationJob(
            id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            schedule=data.schedule,
            job_type=data.job_type,
            payload=data.payload,
            tenant=admin.tenant,
            status='active',
            created_at=datetime.now(timezone.utc)
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return {"id": job.id, "status": "created"}
    finally:
        db.close()

@router.post("/{job_id}/trigger")
def trigger_job(job_id: str, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        job = db.query(AutomationJob).filter(
            AutomationJob.id == job_id,
            AutomationJob.tenant == admin.tenant
        ).first()
        if not job:
            raise HTTPException(404, "Job not found")
        from chronos_v5.tasks import execute_automation_job
        execute_automation_job.delay(job_id)
        return {"status": "triggered", "job_id": job_id}
    finally:
        db.close()

@router.put("/{job_id}")
def update_job(job_id: str, data: JobUpdate, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        job = db.query(AutomationJob).filter(
            AutomationJob.id == job_id,
            AutomationJob.tenant == admin.tenant
        ).first()
        if not job:
            raise HTTPException(404, "Job not found")
        update_data = data.dict(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(job, key):
                setattr(job, key, value)
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "updated"}
    finally:
        db.close()

@router.delete("/{job_id}")
def delete_job(job_id: str, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        job = db.query(AutomationJob).filter(
            AutomationJob.id == job_id,
            AutomationJob.tenant == admin.tenant
        ).first()
        if not job:
            raise HTTPException(404, "Job not found")
        db.delete(job)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()
