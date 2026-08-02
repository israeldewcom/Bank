import time
from functools import wraps
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

# BUG FIX: CircuitBreaker previously held failure_count/state as plain
# instance attributes. That's fine for a true process-wide singleton (e.g.
# api/routers/execution.py's module-level `executor = SettlementExecution()`),
# but chronos_v5/nibss_client.py instantiates a fresh NIBSSClient — and
# therefore a fresh CircuitBreaker — on every single request
# (`client = NIBSSClient(tenant=tenant)` in api/routers/nibss.py), so its
# breaker could never accumulate failures across calls and never actually
# trips. Separately, even the legitimate singleton case breaks down once
# the app runs as more than one process — `workers=4` in main.py/
# advanced_main.py's uvicorn.run(), or replicaCount: 3 in the Helm chart —
# since in-memory state isn't shared across processes or pods.
#
# CircuitBreaker now optionally backs its state with Redis (INCR + EXPIRE
# on a shared key per breaker name) so the same breaker trips consistently
# regardless of how many processes or instances are calling it, or how
# often the wrapping object gets re-instantiated. It falls back to the
# original in-memory behavior if Redis is unavailable, so a Redis outage
# degrades circuit-breaking to per-process (better than crashing outright).
class CircuitBreaker:
    def __init__(self, name, failure_threshold=None, timeout_sec=None, use_redis=True):
        self.name = name
        self.failure_threshold = failure_threshold or Config.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        self.timeout_sec = timeout_sec or Config.CIRCUIT_BREAKER_TIMEOUT_SEC
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"
        self._lock = None
        self._redis = None
        if use_redis:
            try:
                import redis
                self._redis = redis.from_url(Config.REDIS_URL, socket_timeout=1, socket_connect_timeout=1)
                self._redis.ping()
            except Exception as e:
                logger.warning(f"Circuit {self.name}: Redis unavailable, falling back to in-process state: {e}")
                self._redis = None

    def _redis_keys(self):
        return f"cb:{self.name}:count", f"cb:{self.name}:state", f"cb:{self.name}:last_failure"

    def _get_state(self):
        if self._redis is None:
            return self.state, self.failure_count, self.last_failure_time
        try:
            count_key, state_key, last_key = self._redis_keys()
            pipe = self._redis.pipeline()
            pipe.get(count_key)
            pipe.get(state_key)
            pipe.get(last_key)
            count, state, last = pipe.execute()
            count = int(count) if count else 0
            state = state.decode() if state else "CLOSED"
            last = float(last) if last else 0
            return state, count, last
        except Exception as e:
            logger.warning(f"Circuit {self.name}: Redis read failed, using in-process state: {e}")
            return self.state, self.failure_count, self.last_failure_time

    def _record_success(self, was_half_open):
        if self._redis is None:
            if was_half_open:
                self.state = "CLOSED"
                self.failure_count = 0
            return
        try:
            count_key, state_key, _ = self._redis_keys()
            pipe = self._redis.pipeline()
            pipe.delete(count_key)
            pipe.set(state_key, "CLOSED")
            pipe.execute()
        except Exception as e:
            logger.warning(f"Circuit {self.name}: Redis write failed on success: {e}")

    def _record_failure(self):
        now = time.time()
        if self._redis is None:
            self.failure_count += 1
            self.last_failure_time = now
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit {self.name} opened after {self.failure_count} failures")
            return self.failure_count
        try:
            count_key, state_key, last_key = self._redis_keys()
            pipe = self._redis.pipeline()
            pipe.incr(count_key)
            pipe.expire(count_key, self.timeout_sec * 2)
            pipe.set(last_key, now)
            pipe.expire(last_key, self.timeout_sec * 2)
            count, _, _, _ = pipe.execute()
            if count >= self.failure_threshold:
                self._redis.set(state_key, "OPEN")
                logger.warning(f"Circuit {self.name} opened after {count} failures (shared)")
            return count
        except Exception as e:
            logger.warning(f"Circuit {self.name}: Redis write failed on failure: {e}")
            self.failure_count += 1
            return self.failure_count

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            state, count, last_failure_time = self._get_state()
            was_half_open = False
            if state == "OPEN":
                if time.time() - last_failure_time > self.timeout_sec:
                    state = "HALF_OPEN"
                    was_half_open = True
                    logger.info(f"Circuit {self.name} half-open, testing")
                else:
                    raise Exception(f"Circuit {self.name} is OPEN")
            try:
                result = func(*args, **kwargs)
                self._record_success(was_half_open)
                if was_half_open:
                    logger.info(f"Circuit {self.name} closed")
                return result
            except Exception:
                self._record_failure()
                raise
        return wrapper
