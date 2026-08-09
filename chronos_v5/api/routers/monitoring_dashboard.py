# chronos_v5/api/routers/monitoring_dashboard.py
from fastapi import APIRouter, Depends, HTTPException
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.models import User
from chronos_v5.database import SyncSessionLocal
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from sqlalchemy import text
import redis
import os
import platform
from datetime import datetime

router = APIRouter(prefix="/system", tags=["System Monitoring"])

@router.get("/health/detailed")
def detailed_health(current_user: User = Depends(get_current_user)):
    try:
        db = SyncSessionLocal()
        db.execute(text("SELECT 1"))
        db_status = "OK"
    except Exception as e:
        db_status = f"ERROR: {e}"
    finally:
        db.close()

    try:
        r = redis.from_url(Config.REDIS_URL)
        r.ping()
        redis_status = "OK"
    except Exception as e:
        redis_status = f"ERROR: {e}"

    try:
        from chronos_v5.celery_app import celery_app
        i = celery_app.control.inspect()
        stats = i.stats()
        if stats:
            celery_status = f"OK (workers: {len(stats)})"
        else:
            celery_status = "No workers responding"
    except Exception as e:
        celery_status = f"ERROR: {e}"

    try:
        statvfs = os.statvfs('/')
        free_gb = (statvfs.f_bfree * statvfs.f_frsize) / (1024**3)
        disk_status = f"{free_gb:.1f} GB free"
    except:
        disk_status = "N/A"

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Chronos",
        "version": Config.__version__,
        "environment": Config.ENV,
        "tenant": current_user.tenant,
        "components": {
            "database": db_status,
            "redis": redis_status,
            "celery": celery_status,
            "disk_usage": disk_status,
            "platform": platform.platform(),
        }
    }
