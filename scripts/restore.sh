#!/usr/bin/env bash
# Restore a custom-format dump into an isolated database.
#
# Safety: the target may not equal the source, and must end in _restore_test
# unless RESTORE_OVERWRITE_CONFIRM=I_UNDERSTAND_PRODUCTION_RESTORE is set.
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 <backup.dump> [target_database]" >&2
  exit 2
fi

DUMP="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
TARGET="${2:-tmd_restore_test}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-tmd-postgres}"
POSTGRES_DB="${POSTGRES_DB:-tmd}"
POSTGRES_USER="${POSTGRES_USER:-tmd}"
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD.}"

if [ ! -f "$DUMP" ]; then
  echo "Backup not found: $DUMP" >&2
  exit 2
fi
if [ "$TARGET" = "$POSTGRES_DB" ]; then
  echo "Refusing to restore over the source database '$POSTGRES_DB'." >&2
  exit 2
fi
case "$TARGET" in
  *_restore_test) ;;
  *)
    if [ "${RESTORE_OVERWRITE_CONFIRM:-}" != "I_UNDERSTAND_PRODUCTION_RESTORE" ]; then
      echo "Target '$TARGET' is not an isolated test database." >&2
      echo "Use a name ending _restore_test, or set RESTORE_OVERWRITE_CONFIRM explicitly." >&2
      exit 2
    fi
    ;;
esac

echo "Restoring $DUMP into isolated database $TARGET"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
  dropdb -U "$POSTGRES_USER" --if-exists "$TARGET"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
  createdb -U "$POSTGRES_USER" "$TARGET"
docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
  pg_restore -U "$POSTGRES_USER" -d "$TARGET" --no-owner --no-privileges --exit-on-error < "$DUMP"

echo "Restore finished. Verify counts, ledger balance and application start before use."
