replicaCount: 3

image:
  repository: chronos
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 5000

ingress:
  enabled: true
  hostname: chronos-advanced.bank.local
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
  STALE_PRICE_WIDENING_ENABLED: "true"
  LP_OPTIMIZER_ENABLED: "true"
  CBN_EVENT_LISTENER_ENABLED: "true"
  SHADOW_VAR_ENABLED: "true"
  DYNAMIC_CALIBRATION_ENABLED: "true"
  MARKET_IMPACT_ENABLED: "true"
  BACKFILL_TRAINING_ENABLED: "true"
  BACKFILL_CSV_PATH: "/app/historical_settlements.csv"
  SECRET_KEY: "your-strong-secret-key"  # Override
  API_KEY: "your-strong-api-key"
  NIBSS_API_KEY: "your-nibss-key"
