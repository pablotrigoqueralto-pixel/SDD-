#!/bin/sh
# Nightly production backup: pg_dump -Fc, 30-day local retention, external copy.
# Cron (03:30 Europe/Madrid): 30 3 * * * root /opt/quermed-crm/backup.sh
# Any failing step exits non-zero so cron reports it by mail.
set -eu

COMPOSE_DIR="${COMPOSE_DIR:-/opt/quermed-crm}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/quermed-crm}"
RCLONE_REMOTE="${RCLONE_REMOTE:-quermed-backups:quermed-crm}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

cd "$COMPOSE_DIR"
# shellcheck disable=SC1091
. ./.env 2>/dev/null || true
: "${POSTGRES_USER:?POSTGRES_USER missing (source /opt/quermed-crm/.env)}"
: "${POSTGRES_DB:?POSTGRES_DB missing (source /opt/quermed-crm/.env)}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y-%m-%d_%H%M)"
DUMP="$BACKUP_DIR/quermed_crm_${STAMP}.dump"

docker compose --env-file .env -f "$COMPOSE_FILE" exec -T db \
  pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$DUMP"
test -s "$DUMP"

find "$BACKUP_DIR" -name 'quermed_crm_*.dump' -mtime "+$RETENTION_DAYS" -delete

rclone copy "$DUMP" "$RCLONE_REMOTE"

echo "backup ok: $DUMP ($(du -h "$DUMP" | cut -f1)) copied to $RCLONE_REMOTE"
