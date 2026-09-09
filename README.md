# Chronos v5.2.1 — Enterprise Settlement Optimizer

Chronos is a settlement optimization system for the Nigerian banking
ecosystem. It combines machine-learning settlement-failure prediction,
real-time market data, and risk management (VaR / Expected Shortfall /
stress testing) with NIBSS settlement integration.

> **Status:** pre-pilot. Core logic (risk engine, auth, idempotent trade
> ingestion) has unit test coverage and now runs in CI (see "CI status"
> below), but this has **not** been through an external security audit,
> has **not** been validated against live NIBSS/CBN settlement, and its
> risk math has **not** been backtested against independent historical
> data. Treat it as an engineering-complete pilot candidate, not a
> production-approved system, until those three gates are cleared.

## Features

- **Trade Management** — idempotent ingestion, status tracking, CRUD.
- **Settlement Prediction** — XGBoost + online learning, drift detection
  (ADWIN + CUSUM).
- **Collateral Optimization** — dynamic haircuts, LP-based rehypothecation.
- **Risk Management** — VaR, Expected Shortfall, stress testing, Shadow VaR.
  Tenant-scoped: `RiskEngine.compute_all()` requires an explicit `tenant`
  and will not compute a blended, unscoped figure across tenants.
- **Market Data** — Bloomberg, Reuters, Alpha Vantage, Yahoo Finance, NGX, CBN.
- **NIBSS Integration** — settlement API client with circuit breaker.
- **Execution** — FIX protocol support with idempotent retries.
- **Performance Attribution** — P&L tracking, performance fee calculation.
- **Advanced** — dynamic calibration, market impact modeling, CBN event
  listener, backfill training.
- **Observability** — Prometheus metrics, OpenTelemetry, structured logging.
- **Deployment** — Docker Compose, Kubernetes via Helm, SSL renewal.
- **User Management** — multi-tenant, free-trial support, admin panel.

## Quick Start

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in secure values — **never
   commit `.env`**.
3. Build and run with Docker Compose:
   ```bash
   docker-compose -f chronos_v5/deployment/docker-compose.bank.yml up -d
   ```
4. Bootstrap the initial admin user:
   ```bash
   docker-compose exec chronos-api python -m chronos_v5.scripts.bootstrap_admin --output-file /secure/admin_key.txt
   ```

## Running tests locally

```bash
pip install -r requirements.txt pytest pytest-cov
export DATABASE_URL=sqlite:///:memory:
export REDIS_URL=redis://localhost:6379/0
export CHRONOS_ENV=test
export CHRONOS_API_KEY=test-key
export SECRET_KEY=test-secret-key-at-least-32-chars-long
export JWT_SECRET=test-jwt-secret-different-from-secret-key
export ASYNC_DB=false

pytest chronos_v5/test/ -v --cov=chronos_v5 --cov-report=term-missing
```

## Deployment Prerequisites

- PostgreSQL 15+
- Redis 7.2+
- Python 3.11+
- Environment variables — see `.env.example`

## Security

- Never use default passwords in production.
- `ADMIN_PASSWORD`, `JWT_SECRET`, and `SECRET_KEY` must be strong, unique,
  and distinct from each other.
- Use a secrets manager (Vault, AWS Secrets Manager, Kubernetes Secrets)
  for production secrets — never `.env` files on a production host.
- The API refuses to start in production mode if required secrets are
  missing (see `Config.validate()`).
- HSM: if `HSM_ENABLED=false` in production, the app refuses to start
  rather than silently falling back to a software key (see
  `chronos_v5/hsm_abstraction.py`).
- CI runs Bandit (SAST), Gitleaks (secret scanning), and pip-audit
  (dependency CVE scanning) on every push — see `.github/workflows/ci.yml`.
  These gate merges; they do not replace an external audit before a real
  pilot.

## CI Status

CI is defined in `.github/workflows/ci.yml` (lint → security-scan →
unit-tests → smoke-test) and `.github/workflows/release.yaml` (build →
staging deploy → migration → smoke test → production promotion, gated
per-environment).

**Fixes applied to get CI actually running** (previously broken and
silently never executing):

| Issue | Was | Fixed to |
|---|---|---|
| Workflow folder had a literal space in its name, so GitHub never discovered or ran any workflow | `. github/` | `.github/` |
| Unit-test job pointed at a test directory that doesn't exist | `chronos_v5/tests/` | `chronos_v5/test/` |
| Smoke-test job referenced a compose file at a non-existent top-level path | `deployment/docker-compose.bank.yml` | `chronos_v5/deployment/docker-compose.bank.yml` |
| Release workflow's Helm commands pointed at a non-existent nested chart path | `./deployment/helm/chronos` | `./chronos_v5/deployment/helm` |
| Helm values files contained valid YAML but had a `.py` extension, so Helm couldn't load them as `-f` input | `values-bank.py`, `values-advanced.py` | `values-bank.yaml`, `values-advanced.yaml` |
| Seven internal packages shipped with a plain `init.py` instead of `__init__.py`, and four packages (`services/`, `api/middleware/`, `scripts/`, `load_tests/`) — all of which are imported elsewhere as real packages — had **no** `__init__.py` at all. Since nothing had ever successfully run, this had gone undetected. | inconsistent / missing | `__init__.py` present and correctly named everywhere a `.py` file exists |
| No lint config existed, so flake8/black ran with silent, unpinned defaults | none | `.flake8`, `pyproject.toml` added |
| No coverage floor, so coverage could regress silently | none | `--cov-fail-under=70` in CI |

Once these land on `main` and a workflow run goes green, this table
should be deleted — its job is to make the fix auditable once, not to
live in the README permanently.

## Kubernetes Deployment

Helm chart: `chronos_v5/deployment/helm/` (chart.yaml directly inside;
values in `values-bank.yaml` / `values-advanced.yaml`).

- Set `resources.limits` and `resources.requests` per environment.
- Readiness/liveness probes are pre-configured in the chart templates.
- Run migrations via the included `migration-job.yml` (pre-install hook)
  before rolling out a new image — do not rely on app pods to
  self-migrate under load.
- Note: with `replicaCount > 1`, circuit breakers in
  `chronos_v5/circuit_breaker.py` are per-pod, not cluster-wide (see
  comment in `values-bank.yaml`). If a shared breaker is required across
  replicas, back it with Redis instead of an in-process counter.

## Backup & Restore

Scheduled DB backups are controlled via `DB_BACKUP_ENABLED` and
`DB_BACKUP_PATH`. The backup volume must be persistent. Run a restore
drill against `chronos_v5/docs/backup_restore_runbook.md` before relying
on it — an untested runbook is a draft, not a procedure.

## Before a real pilot

This README's "Status" note at the top is the honest summary. Concretely,
before any pilot touches real settlement:

1. Independent security audit / penetration test.
2. Backtest the risk and pricing logic against real, out-of-sample
   historical data (not the repo's synthetic fixtures).
3. A rehearsed cutover using `chronos_v5/docs/production_cutover_checklist.md`,
   including a live restore drill.
4. Confirm CI is green on `main` (see table above) before treating any
   prior review of this codebase as still valid — code review findings
   go stale the moment new commits land.

## Support

For questions or custom deployments, contact the Chronos team.
