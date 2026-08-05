# Production Cutover Checklist – Chronos v5.2.1

## Pre‑Cutover (1 week before)
- [ ] AWS Secrets Manager secrets created and populated for production.
- [ ] IAM role for EKS service account (IRSA) applied and verified.
- [ ] PostgreSQL production instance provisioned with backups enabled.
- [ ] Redis production instance provisioned.
- [ ] Helm chart values for production reviewed (resources, replicas).
- [ ] Dependabot/Snyk scan run, critical/high CVEs remediated.
- [ ] Penetration test completed (admin endpoints, API key lifecycle, NIBSS).
- [ ] Staging deployment successful (Helm migration job, pods healthy, smoke tests).
- [ ] Load test completed with target throughput and latency met.
- [ ] Backup and restore drill executed and RTO/RPO validated.
- [ ] Prometheus metrics exposed and scraped.
- [ ] Alert rules applied, test alerts fired and acknowledged.
- [ ] Grafana dashboards created for key metrics.
- [ ] On‑call rotation set up, runbooks available.
- [ ] Rollback plan documented.

## Go‑Live Day
- [ ] Trigger release pipeline (main branch) and monitor: build, staging, production Helm upgrade with migration job.
- [ ] Verify migration job succeeds.
- [ ] Verify pods become healthy (`kubectl get pods -n production`).
- [ ] Smoke test `/health` and `/trade/` with a test tenant.
- [ ] Verify `Config.validate()` passes in production pod logs.
- [ ] Confirm secrets are loaded correctly.
- [ ] Run a trade ingestion test with real‑looking data.
- [ ] Check NIBSS integration (sandbox or test mode).
- [ ] Monitor initial metrics and alerts.

## Post‑Go‑Live
- [ ] Run a small production pilot (limited volume) for 24 hours.
- [ ] Check P&L attribution and settlement rates.
- [ ] Scale Celery workers and DB connections based on load.
- [ ] Schedule weekly backup and monthly restore drill.

## Rollback Plan
- `helm rollback chronos-prod <revision>`
- `kubectl rollout undo deployment/chronos-prod -n production`
- If database migration fails, restore from backup and revert to previous image.

## Cutover Sign‑Off
- [ ] All pre‑cutover items complete.
- [ ] Go‑live decision made (by product/engineering lead).
- [ ] On‑call engineer notified.

Cutover Date: _______________
Sign‑off: ___________________
