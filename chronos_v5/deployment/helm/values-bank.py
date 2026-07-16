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
  API_KEY: "your-strong-api-key"
  NIBSS_API_KEY: "your-nibss-key"
