# chronos_v5/api/routers/system_workers.py
from fastapi import APIRouter, Depends, HTTPException
from chronos_v5.api.dependencies import get_admin_user
from chronos_v5.models import User
from chronos_v5.celery_app import celery_app
from chronos_v5.logger_setup import logger

router = APIRouter(prefix="/system", tags=["System Workers"])

@router.get("/workers")
def get_workers(admin: User = Depends(get_admin_user)):
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        if not stats:
            return {"workers": [], "message": "No workers responding"}

        active = inspect.active() or {}
        scheduled = inspect.scheduled() or {}
        registered = inspect.registered() or {}

        workers = []
        for worker_name, worker_stats in stats.items():
            workers.append({
                "id": worker_name,
                "status": "active" if worker_stats else "idle",
                "pid": worker_stats.get('pid'),
                "uptime_seconds": worker_stats.get('uptime', 0),
                "active_tasks": len(active.get(worker_name, [])),
                "scheduled_tasks": len(scheduled.get(worker_name, [])),
                "registered_tasks": len(registered.get(worker_name, [])),
            })
        return {"workers": workers}
    except Exception as e:
        logger.error(f"Worker inspection failed: {e}")
        raise HTTPException(500, f"Could not fetch worker data: {str(e)}")
