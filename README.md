# Chronos v5.2.1 - Enterprise Settlement Optimizer

Chronos is a production-grade financial settlement optimization system designed for the Nigerian banking ecosystem. It uses machine learning, real-time market data, and advanced risk management to reduce settlement failures and generate alpha.

## Features

- **Trade Management**: Idempotent ingestion, status tracking, and comprehensive CRUD.
- **Settlement Prediction**: XGBoost model with online learning and concept drift detection (ADWIN + CUSUM).
- **Collateral Optimization**: Dynamic haircut engine, LP-based rehypothecation optimizer.
- **Risk Management**: VaR, Expected Shortfall, Stress Testing, Shadow VaR.
- **Market Data Integration**: Bloomberg, Reuters, Alpha Vantage, Yahoo Finance, NGX, CBN.
- **NIBSS Integration**: Real settlement API with circuit breaker.
- **Execution**: FIX protocol support with retries.
- **Performance Attribution**: P&L tracking, performance fee calculation.
- **Advanced Features**: Dynamic calibration, market impact modeling, CBN event listener, backfill training.
- **Observability**: Prometheus metrics, OpenTelemetry, structured logging.
- **Deployment**: Docker Compose, Kubernetes Helm, SSL renewal.
- **User Management**: Multi-tenant with free trial support, admin panel.

## Quick Start

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in secure values.
3. Build and run with Docker Compose:
   ```bash
   docker-compose -f chronos_v5/deployment/docker-compose.bank.yml up -d
