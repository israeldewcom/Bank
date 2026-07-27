from chronos_v5.celery_app import celery_app
from chronos_v5.logger_setup import logger
from chronos_v5.advanced.advanced_optimizer import AdvancedProfitOptimizer
from chronos_v5.advanced.shadow_var import ShadowVaR
from chronos_v5.advanced.cbn_event_listener import cbn_listener
from chronos_v5.advanced.dynamic_calibrator import DynamicCalibrator
from chronos_v5.advanced.backfill_trainer import BackfillTrainer

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def advanced_optimize(self):
    optimizer = AdvancedProfitOptimizer()
    optimizer.run()

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def advanced_shadow_var(self):
    var = ShadowVaR()
    var.compute_shadow_var()

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def advanced_trigger_cbn_event(self):
    cbn_listener._check_feed()

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def advanced_calibrate(self):
    calibrator = DynamicCalibrator()
    calibrator.force_calibration()

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3
)
def advanced_backfill_train(self):
    trainer = BackfillTrainer()
    trainer.train()
