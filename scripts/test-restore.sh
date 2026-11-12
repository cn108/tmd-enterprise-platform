#!/usr/bin/env bash
# Backup, restore into a separate database, compare evidence, then remove only
# the isolated source and test databases. The live database is never dropped or written.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-tmd_dev_password}"
export POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-tmd-postgres}"
export POSTGRES_DB="${POSTGRES_DB:-tmd}"
export POSTGRES_USER="${POSTGRES_USER:-tmd}"
SOURCE="tmd_restore_source"
TARGET="tmd_restore_test"
TMP_BACKUPS="$(mktemp -d)"
EVIDENCE="$ROOT/docs/reports/evidence/phase-11-restore-test.txt"
mkdir -p "$(dirname "$EVIDENCE")"

q() {
  local database="$1" sql="$2"
  docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
    psql -U "$POSTGRES_USER" -d "$database" -tAc "$sql"
}
cleanup() {
  docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
    dropdb -U "$POSTGRES_USER" --if-exists "$TARGET" >/dev/null 2>&1 || true
  docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
    dropdb -U "$POSTGRES_USER" --if-exists "$SOURCE" >/dev/null 2>&1 || true
  rm -rf "$TMP_BACKUPS"
}
trap cleanup EXIT

# 1. Take a real backup of the live database, then restore it into an isolated
#    source database. The live database is read-only for this whole script.
"$ROOT/scripts/backup.sh" | tee /tmp/tmd-backup-test.log
BASE_DUMP="$(ls -1t "$ROOT"/backups/tmd-*.dump | head -1)"
MEDIA="$(ls -1t "$ROOT"/backups/tmd-media-*.tar.gz | head -1)"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
  dropdb -U "$POSTGRES_USER" --if-exists "$SOURCE"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
  createdb -U "$POSTGRES_USER" "$SOURCE"
docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" "$POSTGRES_CONTAINER" \
  pg_restore -U "$POSTGRES_USER" -d "$SOURCE" --no-owner --no-privileges --exit-on-error < "$BASE_DUMP"

# 2. Put synthetic, balanced ledger data into the isolated source only.
(
  cd "$ROOT/backend"
  POSTGRES_DB="$SOURCE" DJANGO_SETTINGS_MODULE=config.settings.dev \
    ./.venv/Scripts/python.exe - <<'PY'
from datetime import date
from decimal import Decimal
import django

django.setup()

from django.utils import timezone
from apps.accounting.models import Account, AccountingPeriod, FiscalYear
from apps.accounting.services import approve_journal, create_journal, post_journal, submit_journal
from apps.identity.models import User

writer = User.objects.create_user(email="restore-test-writer@example.com", full_name="Restore Writer")
approver = User.objects.create_user(email="restore-test-approver@example.com", full_name="Restore Approver")
cash = Account.objects.create(code="CASH-RESTORE", name="Restore cash", account_type="asset", normal_balance="debit", approved_at=timezone.now())
income = Account.objects.create(code="INCOME-RESTORE", name="Restore income", account_type="income", normal_balance="credit", approved_at=timezone.now())
year = FiscalYear.objects.create(code="FY-RESTORE", name="Restore year", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
period = AccountingPeriod.objects.create(fiscal_year=year, name="Restore January", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
journal = create_journal(
    journal_date=date(2026, 1, 15),
    period=period,
    description="Restore verification journal",
    lines=[
        {"account": cash, "debit": Decimal("125.50"), "credit": Decimal("0")},
        {"account": income, "debit": Decimal("0"), "credit": Decimal("125.50")},
    ],
    actor=writer,
)
submit_journal(journal, writer)
approve_journal(journal, approver)
post_journal(journal, approver)
print(f"Created posted journal {journal.number}")
PY
)

# 3. Back up the isolated source, restore that dump into a second database and
#    compare it with the source.
POSTGRES_DB="$SOURCE" BACKUP_DIR="$TMP_BACKUPS" "$ROOT/scripts/backup.sh" >/dev/null
DUMP="$(ls -1t "$TMP_BACKUPS"/tmd-*.dump | head -1)"
"$ROOT/scripts/restore.sh" "$DUMP" "$TARGET"

SOURCE_MIGRATIONS="$(q "$SOURCE" 'SELECT count(*) FROM django_migrations;')"
RESTORED_MIGRATIONS="$(q "$TARGET" 'SELECT count(*) FROM django_migrations;')"
SOURCE_JOURNALS="$(q "$SOURCE" 'SELECT count(*) FROM accounting_journalentry;')"
RESTORED_JOURNALS="$(q "$TARGET" 'SELECT count(*) FROM accounting_journalentry;')"
SOURCE_LINES="$(q "$SOURCE" 'SELECT count(*) FROM accounting_journalline;')"
RESTORED_LINES="$(q "$TARGET" 'SELECT count(*) FROM accounting_journalline;')"
SOURCE_DEBIT="$(q "$SOURCE" 'SELECT COALESCE(sum(debit),0) FROM accounting_journalline;')"
RESTORED_DEBIT="$(q "$TARGET" 'SELECT COALESCE(sum(debit),0) FROM accounting_journalline;')"
SOURCE_CREDIT="$(q "$SOURCE" 'SELECT COALESCE(sum(credit),0) FROM accounting_journalline;')"
RESTORED_CREDIT="$(q "$TARGET" 'SELECT COALESCE(sum(credit),0) FROM accounting_journalline;')"
FILES_SOURCE="$(find "$ROOT/backend/media" -type f | wc -l | tr -d ' ')"
TMP_MEDIA="$(mktemp -d)"
tar -xzf "$MEDIA" -C "$TMP_MEDIA"
FILES_RESTORED="$(find "$TMP_MEDIA/media" -type f | wc -l | tr -d ' ')"
rm -rf "$TMP_MEDIA"

[ "$SOURCE_MIGRATIONS" = "$RESTORED_MIGRATIONS" ]
[ "$SOURCE_JOURNALS" = "$RESTORED_JOURNALS" ]
[ "$SOURCE_LINES" = "$RESTORED_LINES" ]
[ "$SOURCE_DEBIT" = "$RESTORED_DEBIT" ]
[ "$SOURCE_CREDIT" = "$RESTORED_CREDIT" ]
[ "$SOURCE_DEBIT" = "$SOURCE_CREDIT" ]
[ "$RESTORED_DEBIT" = "125.50" ]
[ "$FILES_SOURCE" = "$FILES_RESTORED" ]

{
  echo "Phase 11 backup and restoration test"
  echo "Executed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Live source database: $POSTGRES_DB (read only)"
  echo "Synthetic verification source: $SOURCE (isolated, removed after verification)"
  echo "Restore target: $TARGET (isolated, removed after verification)"
  echo "Base backup: $(basename "$BASE_DUMP")"
  echo "Base backup SHA256: $(sha256sum "$BASE_DUMP" | awk '{print $1}')"
  echo "Verification dump SHA256: $(sha256sum "$DUMP" | awk '{print $1}')"
  echo "Media archive: $(basename "$MEDIA")"
  echo "Media archive SHA256: $(sha256sum "$MEDIA" | awk '{print $1}')"
  echo
  echo "Migrations: source=$SOURCE_MIGRATIONS restored=$RESTORED_MIGRATIONS"
  echo "Journals: source=$SOURCE_JOURNALS restored=$RESTORED_JOURNALS"
  echo "Journal lines: source=$SOURCE_LINES restored=$RESTORED_LINES"
  echo "Debits: source=$SOURCE_DEBIT restored=$RESTORED_DEBIT"
  echo "Credits: source=$SOURCE_CREDIT restored=$RESTORED_CREDIT"
  echo "Private documents: source=$FILES_SOURCE restored=$FILES_RESTORED"
  echo "Ledger balanced after restore: $([ "$RESTORED_DEBIT" = "$RESTORED_CREDIT" ] && echo yes || echo no)"
  echo "Result: PASS"
} | tee "$EVIDENCE"

echo "Evidence written to $EVIDENCE"
