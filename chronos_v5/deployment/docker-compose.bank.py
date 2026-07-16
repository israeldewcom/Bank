version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: chronos
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-chronos}
      POSTGRES_DB: chronos
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ${DB_BACKUP_PATH:-./backups}:/backups
    ports:
      - "5432:5432"

  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  chronos-api:
    build: .
    ports:
      - "5000:5000"
    environment:
      DATABASE_URL: postgresql://chronos:${POSTGRES_PASSWORD:-chronos}@postgres:5432/chronos
      REDIS_URL: redis://redis:6379/0
      CHRONOS_ENV: production
      CHRONOS_API_KEY: "${API_KEY}"
      SECRET_KEY: "${SECRET_KEY}"
      HSM_ENABLED: "false"
      ASYNC_DB: "true"
      NIBSS_API_KEY: "${NIBSS_API_KEY}"
      BLOOMBERG_API_KEY: "${BLOOMBERG_API_KEY}"
      DB_BACKUP_ENABLED: "true"
      DB_BACKUP_PATH: "/backups"
    depends_on:
      - postgres
      - redis
    volumes:
      - ./models:/app/models
      - ${DB_BACKUP_PATH:-./backups}:/backups

  chronos-celery:
    build: .
    command: celery -A chronos_v5.celery_app worker --loglevel=info -Q celery,alpha,risk,rehypo,advanced
    environment:
      DATABASE_URL: postgresql://chronos:${POSTGRES_PASSWORD:-chronos}@postgres:5432/chronos
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
      SECRET_KEY: "${SECRET_KEY}"
    depends_on:
      - postgres
      - redis
    volumes:
      - ./models:/app/models

  chronos-beat:
    build: .
    command: celery -A chronos_v5.celery_app beat --loglevel=info
    environment:
      CELERY_BROKER_URL: redis://redis:6379/1
    depends_on:
      - redis

volumes:
  pg_data:
  redis_data:
