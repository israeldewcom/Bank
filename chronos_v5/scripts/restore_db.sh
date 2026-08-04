#!/bin/bash
set -e
BACKUP_FILE=$1
TARGET_DB=$2

if [ -z "$BACKUP_FILE" ] || [ -z "$TARGET_DB" ]; then
    echo "Usage: $0 <backup_file.sql.gz> <target_db_url>"
    exit 1
fi
echo "Restoring $BACKUP_FILE to $TARGET_DB"
gunzip -c "$BACKUP_FILE" | psql "$TARGET_DB"
echo "Restore completed."
