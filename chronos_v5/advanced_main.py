"""
Advanced entry point for Chronos v5.2 that starts both original and advanced services.
This file does not modify original main.py; it imports and runs everything together.
"""
import threading, asyncio, uvicorn, time, os
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.database import run_migrations
from chronos_v5.utils.ssl_renewal import ssl_renewal_loop
from chronos_v5.api.app import app
from chronos_v5.nigeria_adapter import nigeria
from chronos_v5.tasks import generate_alpha_signals, optimize_rehypothecation, compute_risk_metrics
from chronos_v5.advanced.advanced_config import AdvancedConfig
from chronos_v5.advanced.cbn_event_listener import cbn_listener
from chronos_v5.advanced.shadow_var import ShadowVaR
from chronos_v5.advanced.advanced_optimizer import AdvancedProfitOptimizer
from chronos_v5.advanced.dynamic_pricing import DynamicPricingEngine
from chronos_v5.advanced.dynamic_calibrator import DynamicCalibrator
from chronos_v5.advanced.backfill_trainer import BackfillTrainer
import redis

def start_advanced_services():
    if not AdvancedConfig.ADVANCED_FEATURES_ENABLED:
        logger.info("Advanced features disabled")
        return
    logger.info("Starting advanced services...")
    # Use Redis lock to ensure only one instance runs these
    r = redis.from_url(Config.REDIS_URL)
    lock_key = "advanced:services:lock"
    lock = r.setnx(lock_key, "1")
    if not lock:
        logger.info("Advanced services already running on another instance")
        return
    r.expire(lock_key, 60)  # lock expires after 60s if crash
    # Start CBN listener
    cbn_listener.start()
    # Start Shadow VaR loop
    def shadow_var_loop():
        var = ShadowVaR()
        var.run_continuous()
    t = threading.Thread(target=shadow_var_loop, daemon=True)
    t.start()
    # Start calibrator loop
    def calibrator_loop():
        calibrator = DynamicCalibrator()
        while True:
            time.sleep(AdvancedConfig.CALIBRATION_INTERVAL_SEC)
            calibrator.calibrate()
    t2 = threading.Thread(target=calibrator_loop, daemon=True)
    t2.start()
    if AdvancedConfig.BACKFILL_TRAINING_ENABLED:
        trainer = BackfillTrainer()
        trainer.train()
    try:
        optimizer = AdvancedProfitOptimizer()
        optimizer.run()
    except Exception as e:
        logger.error(f"Initial advanced optimization failed: {e}")
    logger.info("Advanced services started")

def start_migration():
    logger.info("Running database migrations...")
    run_migrations()
    logger.info("Migrations complete.")

def start_ssl_thread():
    t = threading.Thread(target=ssl_renewal_loop, daemon=True)
    t.start()

def main():
    try:
        Config.validate()
    except RuntimeError as e:
        logger.error(f"Configuration error: {e}")
        raise
    start_migration()
    logger.info("Starting Chronos v5.2.1 Full Production Edition (Advanced) on http://0.0.0.0:5000")
    if Config.PROFILING_ENABLED:
        try:
            import py_spy
            logger.info("Profiling enabled via py-spy")
        except ImportError:
            logger.warning("py-spy not installed")
    start_ssl_thread()
    start_advanced_services()
    try:
        from prometheus_client import start_http_server
        start_http_server(8001)
        logger.info("Prometheus metrics server on :8001")
    except Exception as e:
        logger.warning(f"Prometheus start failed: {e}")
    # Use multiple workers for API, advanced services are in separate threads/locks
    uvicorn.run("chronos_v5.api.app:app", host="0.0.0.0", port=5000,
                log_level=Config.LOG_LEVEL.lower(),
                workers=4, loop="uvloop", http="httptools",
                access_log=False)

if __name__ == "__main__":
    main()
