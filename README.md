```markdown
# Chronos v5.2.1 - Enterprise Settlement Optimizer

Chronos is a production-grade financial settlement optimization system designed for the Nigerian banking ecosystem. It uses machine learning, real-time market data, and advanced risk management to reduce settlement failures and generate alpha.

## Features

- **Trade Management**: Idempotent ingestion, status tracking, comprehensive CRUD.
- **Settlement Prediction**: XGBoost + online learning, drift detection (ADWIN + CUSUM).
- **Collateral Optimization**: Dynamic haircuts, LP-based rehypothecation.
- **Risk Management**: VaR, Expected Shortfall, Stress Testing, Shadow VaR.
- **Market Data Integration**: Bloomberg, Reuters, Alpha Vantage, Yahoo Finance, NGX, CBN.
- **NIBSS Integration**: Real settlement API with circuit breaker.
- **Execution**: FIX protocol support with idempotent retries.
- **Performance Attribution**: P&L tracking, performance fee calculation.
- **Advanced Features**: Dynamic calibration, market impact modeling, CBN event listener, backfill training.
- **Observability**: Prometheus metrics, OpenTelemetry, structured logging.
- **Deployment**: Docker Compose, Kubernetes Helm, SSL renewal.
- **User Management**: Multi-tenant with free trial support, admin panel.

## Quick Start

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in secure values – **never commit `.env`**.
3. Build and run with Docker Compose:
   ```bash
   docker-compose -f deployment/docker-compose.bank.yml up -d
```

4. Bootstrap the initial admin user:
   ```bash
   docker-compose exec chronos-api python -m scripts.bootstrap_admin --output-file /secure/admin_key.txt
   ```

Deployment Prerequisites

· PostgreSQL 15+
· Redis 7.2+
· Python 3.11+
· Environment variables (see .env.example)

Security

· Never use default passwords in production.
· ADMIN_PASSWORD, JWT_SECRET, and SECRET_KEY must be strong and unique.
· Use a secrets manager (Vault, AWS Secrets Manager, Kubernetes Secrets) for production secrets.
· The API will fail to start if required secrets are missing in production mode.

Continuous Integration

A GitHub Actions workflow (.github/workflows/ci.yml) is provided. It runs linters, unit tests, and a smoke test on every push and pull request.

Kubernetes Deployment

Helm charts are located in deployment/helm/chronos/. For production:

· Set appropriate resources.limits and requests.
· Enable readiness and liveness probes (already configured).
· Use the included migration-job.yaml (pre-install hook) to run database migrations before rolling out new versions.

Backup & Restore

Scheduled DB backups are enabled via DB_BACKUP_ENABLED and DB_BACKUP_PATH. Ensure the backup volume is persistent and test restore procedures regularly.

Support

For questions or custom deployments, contact the Chronos team.

```
