# chronos_v5/tasks.py — compute_risk_metrics task, corrected
@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def compute_risk_metrics(self):
    """
    RELIABILITY FIX: previously called engine.compute_all() with no
    arguments. RiskEngine.compute_all() used to accept a falsy/None tenant
    and silently compute VaR/ES/stress loss across every tenant's trades
    merged together, then persist that blended figure mislabeled under
    tenant "default" — a materially wrong risk number for any bank relying
    on it, not just a missing-filter bug. compute_all() now requires tenant
    and raises if it's missing, so this task must (and now does) iterate
    every real tenant from TenantConfig and compute risk metrics once per
    tenant, matching how every other per-tenant read/write path in this
    codebase works.
    """
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
