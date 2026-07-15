import logging
import sys
import json
from datetime import datetime
from chronos_v5.config import Config

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "correlation_id"):
            log_record["correlation_id"] = record.correlation_id
        return json.dumps(log_record)

def setup_logger():
    logger = logging.getLogger("chronos")
    logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    if Config.LOG_JSON:
        handler.setFormatter(JsonFormatter())
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
    logger.addHandler(handler)
    if Config.LOG_FILE:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(Config.LOG_FILE, maxBytes=Config.LOG_MAX_BYTES, backupCount=Config.LOG_BACKUP_COUNT)
        fh.setFormatter(handler.formatter)
        logger.addHandler(fh)
    return logger

logger = setup_logger()
