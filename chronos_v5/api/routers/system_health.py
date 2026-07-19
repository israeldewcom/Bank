from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from chronos_v5.database import SyncSessionLocal
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from sqlalchemy import text
import redis
import os
import platform
from datetime import datetime

router = APIRouter(prefix="/system", tags=["System"])

def get_redis_status():
    try:
        r = redis.from_url(Config.REDIS_URL)
        r.ping()
        return "OK"
    except Exception as e:
        return f"ERROR: {e}"

def get_db_status():
    try:
        db = SyncSessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return "OK"
    except Exception as e:
        return f"ERROR: {e}"

def get_celery_status():
    try:
        from chronos_v5.celery_app import celery_app
        i = celery_app.control.inspect()
        stats = i.stats()
        if stats:
            return "OK (workers: {})".format(len(stats))
        else:
            return "No workers responding"
    except Exception as e:
        return f"ERROR: {e}"

@router.get("/health/detailed")
def detailed_health(request: Request):
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Chronos",
        "version": Config.__version__,
        "environment": Config.ENV,
        "tenant": request.headers.get(Config.TENANT_HEADER, Config.DEFAULT_TENANT),
        "components": {
            "database": get_db_status(),
            "redis": get_redis_status(),
            "celery": get_celery_status(),
            "disk_usage": f"{os.statvfs('/').f_bfree * os.statvfs('/').f_frsize / (1024**3):.1f} GB free",
            "platform": platform.platform(),
        }
    }

@router.get("/health/dashboard", response_class=HTMLResponse)
def health_dashboard():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Chronos System Health</title>
        <style>
            body { font-family: Arial; background: #1e1e2f; color: #fff; padding: 2rem; }
            .card { background: #2d2d44; border-radius: 12px; padding: 1.5rem; margin: 1rem 0; }
            .ok { color: #4caf50; }
            .error { color: #f44336; }
            .warn { color: #ff9800; }
        </style>
    </head>
    <body>
        <h1>🔍 Chronos System Health</h1>
        <div class="card">
            <h2>Components</h2>
            <ul id="health-list">
                <li>Database: <span id="db-status">Loading...</span></li>
                <li>Redis: <span id="redis-status">Loading...</span></li>
                <li>Celery: <span id="celery-status">Loading...</span></li>
                <li>Disk: <span id="disk-status">Loading...</span></li>
            </ul>
        </div>
        <div class="card">
            <h2>Tenant Info</h2>
            <p>Tenant: <span id="tenant"></span></p>
            <p>Environment: <span id="env"></span></p>
            <p>Version: <span id="version"></span></p>
        </div>
        <script>
            async function fetchHealth() {
                const res = await fetch('/system/health/detailed');
                const data = await res.json();
                document.getElementById('tenant').textContent = data.tenant || 'N/A';
                document.getElementById('env').textContent = data.environment || 'N/A';
                document.getElementById('version').textContent = data.version || 'N/A';

                const db = data.components.database;
                document.getElementById('db-status').textContent = db;
                document.getElementById('db-status').className = db === 'OK' ? 'ok' : 'error';

                const redis = data.components.redis;
                document.getElementById('redis-status').textContent = redis;
                document.getElementById('redis-status').className = redis === 'OK' ? 'ok' : 'error';

                const celery = data.components.celery;
                document.getElementById('celery-status').textContent = celery;
                document.getElementById('celery-status').className = celery.startsWith('OK') ? 'ok' : 'error';

                document.getElementById('disk-status').textContent = data.components.disk_usage || 'Unknown';
            }
            fetchHealth();
            setInterval(fetchHealth, 30000);
        </script>
    </body>
    </html>
    """
    return html
