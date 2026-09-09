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
