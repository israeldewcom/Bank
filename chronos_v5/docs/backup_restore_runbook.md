# DB Backup & Restore Runbook

## Backup
- Scheduled: cron job runs `scripts/backup_db.sh` daily at 02:00 UTC.
- Retention: 7 daily, 4 weekly.
- Location: `/backups` (mounted persistent volume) and optionally off‑site to S3.

## Restore Procedure
1. Identify the backup file (e.g., `chronos_backup_20250803_020000.sql.gz`).
2. Ensure target database is empty or prepared.
3. Run: `./scripts/restore_db.sh /backups/chronos_backup_20250803_020000.sql.gz "postgresql://user:pass@host:5432/target"`
4. Run smoke tests: `/health`, `/trade/` with a test tenant.

## Testing Restore
- Monthly restore drill on staging to validate integrity and RTO.
