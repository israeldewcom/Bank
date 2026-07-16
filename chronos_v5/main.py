import threading, asyncio, uvicorn, time, os
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.database import run_migrations
from chronos_v5.utils.ssl_renewal import ssl_renewal_loop
from chronos_v5.api.app import app
from chronos_v5.nigeria_adapter import nigeria
from chronos_v5.tasks import generate_alpha_signals, optimize_rehypothecation, compute_risk_metrics

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
    logger.info("Starting Chronos v5.2.1 Full Production Edition on http://0.0.0.0:5000")
    if Config.PROFILING_ENABLED:
        try:
            import py_spy
            logger.info("Profiling enabled via py-spy")
        except ImportError:
            logger.warning("py-spy not installed")
    start_ssl_thread()
    try:
        from prometheus_client import start_http_server
        start_http_server(8001)
        logger.info("Prometheus metrics server on :8001")
    except Exception as e:
        logger.warning(f"Prometheus start failed: {e}")
    # Use multiple workers, but ensure advanced services are started only once via lock
    # We'll start advanced services in a separate process or with lock, but for simplicity we'll rely on celery.
    uvicorn.run("chronos_v5.api.app:app", host="0.0.0.0", port=5000,
                log_level=Config.LOG_LEVEL.lower(),
                workers=4, loop="uvloop", http="httptools",
                access_log=False)

if __name__ == "__main__":
    main()
