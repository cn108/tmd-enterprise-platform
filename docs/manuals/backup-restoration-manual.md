# Backup and restoration manual

## 1. What is protected

- PostgreSQL database, including ledger, audit and configuration.
- Private uploaded documents under `backend/media`.
- Deployment secrets/configuration (managed separately, never inside the backup archive).

## 2. Backup procedure

```bash
export POSTGRES_PASSWORD='...'
export BACKUP_DIR=/secure/backups
export POSTGRES_CONTAINER=tmd-postgres
export POSTGRES_DB=tmd_production
export POSTGRES_USER=tmd
./scripts/backup.sh
```

The script creates:

- a custom-format PostgreSQL dump;
- a media archive;
- a JSON manifest with timestamp, database name, SHA-256 checksums, migration count and retention;
- `.sha256` sidecar files.

`REQUIRE_EXPLICIT_BACKUP=1` refuses a production backup that still uses the development database name `tmd`.

## 3. Encryption and storage

The script does **not** encrypt the archive itself. Production must store backups on encrypted storage with restricted access and an object-store lifecycle rule. Keep at least one copy off the production host. A backup is not proven until the manifest, checksum and restore test are verified.

## 4. Retention

Default local retention is 30 days (`BACKUP_RETENTION_DAYS`). Proposed provisional policy for management review:

- daily backups: 30 days
- monthly backups: 12 months
- annual/statutory retention: per TMD's legal and tax obligations
- restore test: at least quarterly, and after any schema change

## 5. Restore test

Always restore into an isolated database name ending `_restore_test`:

```bash
export POSTGRES_PASSWORD='...'
./scripts/restore.sh /secure/backups/tmd-YYYYMMDDTHHMMSSZ.dump tmd_restore_test
```

The script refuses to restore over the source database or a non-test name without explicit confirmation.

Verify in the isolated database:

1. migration count;
2. row counts for key tables;
3. posted journal debit/credit totals balance;
4. document count and checksum sample;
5. application starts against the restored database and a read-only report loads.

A restore command that exits zero is not sufficient. Record the verification evidence. The latest isolated test is in `docs/reports/evidence/phase-11-restore-test.txt`.

## 6. Disaster recovery

1. Declare the incident and freeze writes.
2. Identify the last verified backup before the incident.
3. Provision a clean host or database.
4. Restore database and media.
5. Apply only migrations present in the release.
6. Validate ledger balance, reconciliation status and document access.
7. Reconnect users after management authorisation.
8. Record data loss between the recovery point and the incident.

## 7. Recovery objectives (provisional)

| Objective | Proposed default | Status |
| --- | --- | --- |
| RPO | 24 hours | Provisional; management must approve |
| RTO | 8 hours | Provisional; depends on host and backup location |
| Restore test frequency | Quarterly | Provisional |

These are not approved service commitments.

## 8. Failure handling

- Non-zero backup exit: no usable backup; investigate immediately.
- Checksum mismatch: do not restore; obtain another copy.
- Restore error: stop, preserve logs, retry with a fresh target.
- Missing media: database is usable but document evidence is incomplete; escalate.
