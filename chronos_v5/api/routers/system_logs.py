# chronos_v5/api/routers/system_logs.py
import os
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from chronos_v5.api.dependencies import get_admin_user
from chronos_v5.models import User
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

router = APIRouter(prefix="/system", tags=["System Logs"])

@router.get("/logs")
def get_logs(
    level: str = Query(None, regex="^(INFO|WARN|ERROR|DEBUG)$"),
    limit: int = Query(50, ge=1, le=500),
    admin: User = Depends(get_admin_user)
):
    log_file = Config.LOG_FILE
    if not os.path.exists(log_file):
        return {"logs": [], "message": "Log file not found"}

    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        lines = lines[::-1]
        filtered = []
        for line in lines:
            if level:
                if re.search(r'\b' + level + r'\b', line, re.IGNORECASE):
                    filtered.append(line.strip())
            else:
                filtered.append(line.strip())
            if len(filtered) >= limit:
                break
        if Config.LOG_JSON:
            import json
            logs = []
            for line in filtered:
                try:
                    logs.append(json.loads(line))
                except:
                    logs.append({"raw": line})
        else:
            logs = [{"raw": line} for line in filtered]
        return {"logs": logs, "count": len(logs)}
    except Exception as e:
        logger.error(f"Failed to read logs: {e}")
        raise HTTPException(500, f"Could not read logs: {str(e)}")
