replicaCount: 3

# NOTE: with replicaCount > 1, each pod has independent in-memory state.
# chronos_v5/circuit_breaker.py's CircuitBreaker and chronos_v5/database.py's
# run_migrations() local lock file are both per-process/per-pod, not shared
# across replicas. That's fine for run_migrations() (Helm should run
# migrations via a pre-install/pre-upgrade Job with a single replica, not
# rely on the app pods to self-migrate under load), but it does mean the
# NIBSS/execution circuit breakers can trip independently per pod rather
# than cluster-wide. If a shared breaker is required, back CircuitBreaker
# with Redis (INCR + EXPIRE on a shared key) instead of local counters.

image:
  repository: chronos
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  # BUG FIX: this was 5000, matching chronos_v5/main.py's old default
  # rather than the Dockerfile's actual --port 8000. Standardized on
  # 8000 across Dockerfile, main.py, docker-compose, and this chart.
  port: 8000

ingress:
  enabled: true
  hostname: chronos.bank.local
  tls: true

postgres:
  host: postgres
  user: chronos
  password: chronos
  database: chronos

redis:
  host: redis
  port: 6379

celery:
  workerConcurrency: 4

env:
  CHRONOS_ENV: production
  ASYNC_DB: "true"
  ADVANCED_FEATURES_ENABLED: "true"
  SECRET_KEY: "your-strong-secret-key"  # Override with actual secret
  # BUG FIX: JWT_SECRET was missing from this chart entirely. Config.py
  # requires JWT_SECRET to be explicitly set and different from SECRET_KEY
  # in production (see Config.validate()) — without this key the app
  # either fails to boot in production or silently falls back to reusing
  # SECRET_KEY, which Config.validate() is specifically designed to reject.
  JWT_SECRET: "your-separate-strong-jwt-secret"  # Override with actual secret, must differ from SECRET_KEY
  API_KEY: "your-strong-api-key"
  NIBSS_API_KEY: "your-nibss-key"
