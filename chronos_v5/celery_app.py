from celery import Celery
from chronos_v5.config import Config
import os

# BUG FIX: this referenced chronos_v5.advanced.advanced_tasks (plural),
# but the actual file is chronos_v5/advanced/advanced_task.py (singular).
# Celery's include list uses importlib under the hood, so this module
# failed to import at worker startup — advanced_optimize,
# advanced_shadow_var, advanced_trigger_cbn_event, advanced_calibrate,
# and advanced_backfill_train (all defined in that file) never registered
# with the worker and could never be dispatched or scheduled.
celery_app = Celery(
    "chronos",
    broker=Config.CELERY_BROKER_URL,
    backend=Config.CELERY_RESULT_BACKEND,
    include=["chronos_v5.tasks", "chronos_v5.advanced.advanced_task"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_time_limit=Config.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=Config.CELERY_TASK_SOFT_TIME_LIMIT,
    task_always_eager=Config.CELERY_TASK_ALWAYS_EAGER,
    result_expires=3600,
)

if Config.REDIS_SENTINEL:
    celery_app.conf.broker_transport_options = {
        "master_name": Config.REDIS_SENTINEL_MASTER,
        "sentinels": Config.REDIS_SENTINEL.split(",")
    }
