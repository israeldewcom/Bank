# chronos_v5/api/routers/system_queues.py
from fastapi import APIRouter, Depends, HTTPException
from chronos_v5.api.dependencies import get_admin_user
from chronos_v5.models import User
from chronos_v5.celery_app import celery_app
from chronos_v5.logger_setup import logger

router = APIRouter(prefix="/system", tags=["System Queues"])

@router.get("/queues")
def get_queues(admin: User = Depends(get_admin_user)):
    try:
        inspect = celery_app.control.inspect()
        active = inspect.active_queues()
        if not active:
            return {"queues": [], "message": "No workers responding"}

        queue_lengths = {}
        for worker, queues in active.items():
            for q in queues:
                name = q.get('name')
                if name:
                    queue_lengths[name] = queue_lengths.get(name, 0) + 1

        stats = inspect.stats()
        tasks = inspect.active()
        scheduled = inspect.scheduled()

        result = {
            "queues": [
                {
                    "name": name,
                    "length": queue_lengths.get(name, 0),
                    "active_tasks": len([t for t in tasks.values() if t.get('queue') == name]) if tasks else 0,
                    "scheduled_tasks": len([t for t in scheduled.values() if t.get('queue') == name]) if scheduled else 0,
                }
                for name in queue_lengths.keys()
            ]
        }
        return result
    except Exception as e:
        logger.error(f"Queue inspection failed: {e}")
        raise HTTPException(500, f"Could not fetch queue data: {str(e)}")
