#!/bin/bash
set -e
DB_URL=${1:-$DATABASE_URL}
BACKUP_PATH=${2:-/backups}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="chronos_backup_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_PATH"
echo "Starting backup to $BACKUP_PATH/$FILENAME"
pg_dump "$DB_URL" | gzip > "$BACKUP_PATH/$FILENAME"
find "$BACKUP_PATH" -name "chronos_backup_*.sql.gz" -mtime +7 -delete
echo "Backup completed: $FILENAME"
