#!/usr/bin/env bash
# Create a custom-format PostgreSQL dump plus a private-document archive.
#
# Credentials come from the environment. The development defaults match
# infra/docker-compose.yml; staging and production must set every variable.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-tmd-postgres}"
POSTGRES_DB="${POSTGRES_DB:-tmd}"
POSTGRES_USER="${POSTGRES_USER:-tmd}"
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD; no production default is provided.}"

umask 077
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP="$BACKUP_DIR/tmd-$STAMP.dump"
MEDIA="$BACKUP_DIR/tmd-media-$STAMP.tar.gz"
META="$BACKUP_DIR/tmd-$STAMP.json"

if [ "${REQUIRE_EXPLICIT_BACKUP:-0}" = "1" ] && [ "$POSTGRES_DB" = "tmd" ]; then
  echo "Refusing a production backup with the development database name 'tmd'." >&2
  exit 2
fi

echo "Backing up database '$POSTGRES_DB' to $DUMP"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --format=custom --no-owner --no-privileges > "$DUMP"

echo "Backing up private documents to $MEDIA"
tar -czf "$MEDIA" -C "$ROOT/backend" media

DUMP_SHA="$(sha256sum "$DUMP" | awk '{print $1}')"
MEDIA_SHA="$(sha256sum "$MEDIA" | awk '{print $1}')"
COUNT="$(docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT count(*) FROM django_migrations;")"

cat > "$META" <<JSON
{
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "database": "$POSTGRES_DB",
  "database_dump": "$(basename "$DUMP")",
  "database_sha256": "$DUMP_SHA",
  "migrations_recorded": $COUNT,
  "media_archive": "$(basename "$MEDIA")",
  "media_sha256": "$MEDIA_SHA",
  "retention_days": $RETENTION_DAYS,
  "encryption": "storage-layer encryption required; archive itself is not encrypted by this script"
}
JSON

echo "$DUMP_SHA  $(basename "$DUMP")" > "$DUMP.sha256"
echo "$MEDIA_SHA  $(basename "$MEDIA")" > "$MEDIA.sha256"

# Retention is local only; production also requires object-store lifecycle rules.
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'tmd-*' -mtime "+$RETENTION_DAYS" -delete

echo "Backup complete:"
echo "  $DUMP"
echo "  $MEDIA"
echo "  $META"
echo "Record the manifest in the backup monitoring system. A non-zero exit means no usable backup."
