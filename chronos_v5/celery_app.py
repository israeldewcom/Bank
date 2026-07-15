from celery import Celery
from chronos_v5.config import Config
import os

celery_app = Celery(
    "chronos",
    broker=Config.CELERY_BROKER_URL,
    backend=Config.CELERY_RESULT_BACKEND,
    include=["chronos_v5.tasks", "chronos_v5.advanced.advanced_tasks"]
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
