import time
from functools import wraps
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

class CircuitBreaker:
    def __init__(self, name, failure_threshold=None, timeout_sec=None):
        self.name = name
        self.failure_threshold = failure_threshold or Config.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        self.timeout_sec = timeout_sec or Config.CIRCUIT_BREAKER_TIMEOUT_SEC
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"
        self._lock = None

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.timeout_sec:
                    self.state = "HALF_OPEN"
                    logger.info(f"Circuit {self.name} half-open, testing")
                else:
                    raise Exception(f"Circuit {self.name} is OPEN")
            try:
                result = func(*args, **kwargs)
                if self.state == "HALF_OPEN":
                    self.state = "CLOSED"
                    self.failure_count = 0
                    logger.info(f"Circuit {self.name} closed")
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    logger.warning(f"Circuit {self.name} opened after {self.failure_count} failures")
                raise
        return wrapper
