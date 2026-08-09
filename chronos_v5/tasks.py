# chronos_v5/tasks.py
from chronos_v5.celery_app import celery_app
from chronos_v5.logger_setup import logger
from chronos_v5.config import Config
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import BackupRecord, AutomationJob, PnLAttribution
import subprocess
import os
from datetime import datetime, timezone, timedelta

# ============================================================
# EXISTING TASKS (keep these)
# ============================================================

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def attribute_pnl(self, trade_id: str, strategy: str, amount_saved: float, tenant: str = "default"):
    db = SyncSessionLocal()
    try:
        pnl = PnLAttribution(
            trade_id=trade_id,
            strategy=strategy,
            amount_saved=amount_saved,
            currency="NGN",
            metadata_json='{"source": "predictor"}',
            tenant=tenant
        )
        db.add(pnl)
        db.commit()
        if Config.PERFORMANCE_FEE_ENABLED:
            fee = amount_saved * Config.PERFORMANCE_FEE_PERCENT
            logger.info(f"Performance fee accrued: {fee} NGN on trade {trade_id} for tenant {tenant}")
    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def generate_alpha_signals(self):
    from chronos_v5.market_data import MarketDataAggregator
    from chronos_v5.models import AlphaSignal
    from chronos_v5.database import SyncSessionLocal
    aggregator = MarketDataAggregator()
    signals = aggregator.compute_alpha()
    db = SyncSessionLocal()
    for asset, value in signals.items():
        sig = AlphaSignal(asset=asset, signal_value=value, strategy=Config.ALPHA_STRATEGY_TYPE)
        db.add(sig)
    db.commit()
    db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def optimize_rehypothecation(self):
    from chronos_v5.profit_optimizer import ProfitOptimizer
    from chronos_v5.models import TenantConfig
    from chronos_v5.database import SyncSessionLocal
    db = SyncSessionLocal()
    try:
        tenants = [row.tenant for row in db.query(TenantConfig.tenant).all()]
    finally:
        db.close()
    if not tenants:
        logger.warning("optimize_rehypothecation: no tenants found; nothing to optimize")
        return
    for tenant in tenants:
        try:
            optimizer = ProfitOptimizer(tenant=tenant)
            optimizer.run()
        except Exception as e:
            logger.error(f"optimize_rehypothecation failed for tenant {tenant}: {e}")


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def compute_risk_metrics(self):
    from chronos_v5.risk_engine import RiskEngine
    from chronos_v5.models import TenantConfig
    from chronos_v5.database import SyncSessionLocal

    engine = RiskEngine()
    db = SyncSessionLocal()
    try:
        tenants = [row.tenant for row in db.query(TenantConfig.tenant).all()]
    finally:
        db.close()

    if not tenants:
        logger.warning("compute_risk_metrics: no tenants found in TenantConfig; nothing to compute")
        return

    for tenant in tenants:
        try:
            engine.compute_all(tenant=tenant)
        except Exception as e:
            logger.error(f"compute_risk_metrics failed for tenant {tenant}: {e}")

# ============================================================
# NEW TASKS (add these)
# ============================================================

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def create_database_backup(self, backup_id: str, tenant: str):
    """
    Create a database backup for a tenant.
    """
    db = SyncSessionLocal()
    record = None
    try:
        record = db.query(BackupRecord).filter(BackupRecord.id == backup_id).first()
        if not record:
            logger.error(f"Backup record {backup_id} not found")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chronos_backup_{tenant}_{timestamp}.sql.gz"
        filepath = os.path.join(Config.DB_BACKUP_PATH, filename)

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        cmd = f"pg_dump {Config.DATABASE_URL} | gzip > {filepath}"
        subprocess.check_call(cmd, shell=True)

        record.file_path = filepath
        record.size_bytes = os.path.getsize(filepath)
        record.status = "completed"
        record.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Backup completed: {filepath} for tenant {tenant}")

        # Clean old backups
        self._clean_old_backups(tenant)

    except Exception as e:
        if record:
            record.status = "failed"
            record.error_message = str(e)
            db.commit()
        logger.error(f"Backup failed for tenant {tenant}: {e}")
        raise
    finally:
        db.close()

    @celery_app.task(bind=True)
    def _clean_old_backups(self, tenant: str):
        """Clean backups older than retention days."""
        db = SyncSessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=Config.BACKUP_RETENTION_DAYS)
            old_backups = db.query(BackupRecord).filter(
                BackupRecord.tenant == tenant,
                BackupRecord.completed_at < cutoff
            ).all()
            for backup in old_backups:
                if backup.file_path and os.path.exists(backup.file_path):
                    try:
                        os.remove(backup.file_path)
                        logger.info(f"Removed old backup: {backup.file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to remove old backup {backup.file_path}: {e}")
                db.delete(backup)
            db.commit()
        finally:
            db.close()
        return {"cleaned": len(old_backups)}


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def restore_database_backup(self, filepath: str, tenant: str):
    """
    Restore a database backup for a tenant.
    """
    if not os.path.exists(filepath):
        logger.error(f"Backup file not found: {filepath}")
        raise FileNotFoundError(f"Backup file not found: {filepath}")

    try:
        cmd = f"gunzip -c {filepath} | psql {Config.DATABASE_URL}"
        subprocess.check_call(cmd, shell=True)
        logger.info(f"Restore completed from {filepath} for tenant {tenant}")
        return {"status": "restored", "file": filepath, "tenant": tenant}
    except Exception as e:
        logger.error(f"Restore failed for tenant {tenant}: {e}")
        raise


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def execute_automation_job(self, job_id: str):
    """
    Execute an automation job.
    """
    db = SyncSessionLocal()
    job = None
    try:
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        job.status = "running"
        db.commit()

        if job.job_type == "backup":
            from chronos_v5.tasks import create_database_backup
            result = create_database_backup.delay(None, job.tenant)
            job.payload = {"task_id": result.id}
        elif job.job_type == "recalibrate":
            from chronos_v5.advanced.dynamic_calibrator import DynamicCalibrator
            calibrator = DynamicCalibrator()
            success = calibrator.force_calibration()
            job.payload = {"success": success}
        elif job.job_type == "risk":
            from chronos_v5.tasks import compute_risk_metrics
            compute_risk_metrics.delay()
        elif job.job_type == "rehypothecation":
            from chronos_v5.tasks import optimize_rehypothecation
            optimize_rehypothecation.delay()
        elif job.job_type == "report":
            # Generate report logic
            job.payload = {"status": "report_generated", "timestamp": datetime.now(timezone.utc).isoformat()}
        else:
            logger.warning(f"Unknown job type: {job.job_type}")
            job.payload = {"error": f"Unknown job type: {job.job_type}"}

        job.status = "active"
        job.last_run = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Job {job_id} ({job.name}) executed successfully")

    except Exception as e:
        if job:
            job.status = "failed"
            job.payload = {"error": str(e)}
            db.commit()
        logger.error(f"Job {job_id} failed: {e}")
        raise
    finally:
        db.close()

    return {"job_id": job_id, "status": "completed"}


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def schedule_automation_jobs(self):
    """
    Schedule all automation jobs that need to run.
    This task should be called by Celery Beat periodically.
    """
    db = SyncSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        jobs = db.query(AutomationJob).filter(
            AutomationJob.status == "active",
            AutomationJob.next_run <= now
        ).all()

        for job in jobs:
            execute_automation_job.delay(job.id)
            # Update next_run based on schedule
            if job.schedule.startswith("daily"):
                job.next_run = now + timedelta(days=1)
            elif job.schedule.startswith("hourly"):
                job.next_run = now + timedelta(hours=1)
            elif job.schedule.startswith("weekly"):
                job.next_run = now + timedelta(days=7)
            else:
                job.next_run = now + timedelta(hours=1)  # default
            db.commit()

        return {"scheduled": len(jobs)}
    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def send_webhook_event(self, webhook_id: str, event: str, payload: dict):
    """
    Send a webhook event to a webhook endpoint.
    """
    from chronos_v5.database import SyncSessionLocal
    from chronos_v5.models import Webhook
    import requests
    import json
    import hmac
    import hashlib

    db = SyncSessionLocal()
    try:
        webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
        if not webhook:
            logger.error(f"Webhook {webhook_id} not found")
            return

        if webhook.status != "active":
            logger.info(f"Webhook {webhook_id} is not active, skipping")
            return

        if event not in webhook.events and "all" not in webhook.events:
            logger.info(f"Webhook {webhook_id} not subscribed to event {event}")
            return

        headers = {"Content-Type": "application/json"}
        if webhook.secret:
            signature = hmac.new(
                webhook.secret.encode(),
                json.dumps(payload).encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = signature

        resp = requests.post(
            webhook.url,
            json=payload,
            headers=headers,
            timeout=Config.WEBHOOK_TIMEOUT_SEC
        )
        resp.raise_for_status()

        webhook.last_triggered = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Webhook {webhook_id} triggered for event {event}")
        return {"status": "sent", "response_code": resp.status_code}

    except Exception as e:
        logger.error(f"Webhook {webhook_id} failed: {e}")
        # Could mark webhook as failed after too many retries
        raise
    finally:
        db.close()
