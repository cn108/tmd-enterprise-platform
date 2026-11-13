# Maintenance procedures

## 1. Routine maintenance

| Frequency | Task | Owner | Evidence |
| --- | --- | --- | --- |
| Daily | Check health endpoints, error rate, failed sign-ins and backup completion | Software Administrator | Monitoring dashboard / log entry |
| Daily | Confirm no backup job failed and the latest manifest checksum exists | Operations | Backup manifest |
| Weekly | Review audit exceptions, locked accounts and stale approvals | Administrator / Finance Controller | Review note |
| Weekly | Check disk, database size, certificate expiry and queue/worker health if enabled | Administrator | Capacity note |
| Monthly | Apply approved security patches in staging, run regression, then production | Administrator | Change record |
| Monthly | Reconcile backup retention and confirm one off-host copy is restorable | Operations | Restore evidence |
| Quarterly | Full isolated restore drill, credential review and access recertification | Administrator / Management | Signed drill record |
| Annually | Secret rotation plan, disaster-recovery exercise and statutory retention review | Management / IT | Approved plan |

## 2. Change control

1. Record the change, reason and rollback method.
2. Take a verified backup before a schema or configuration change.
3. Test in staging with production-like settings; never test with live data.
4. Obtain approval for financial or access-control changes.
5. Deploy outside active processing where possible.
6. Verify health, sign-in, MFA, a read-only report and one audited non-financial write.
7. Record the release, migration numbers, approver and result.

Do not run `migrate --fake`, edit applied migrations, delete audit rows or reset the database to clear an error.

## 3. Dependency and security updates

- Review Python and npm advisories before each release.
- Pin and test upgrades in a branch; do not upgrade production directly.
- Re-run backend tests, frontend tests, lint, build, migration drift and the production system check.
- Record accepted risks with an owner and expiry date.

## 4. Certificate and domain maintenance

- Monitor certificate expiry at 30, 14 and 7 days.
- Renew before expiry and verify the full chain from an external client.
- Keep the private key outside the repository.
- Changing the domain requires updating `TMD_DOMAIN`, TLS, CSRF trusted origins and email links.

## 5. Database maintenance

- Use `VACUUM`/autovacuum monitoring and index-health checks on the production database.
- Do not run manual `VACUUM FULL` during business hours.
- Investigate slow queries before adding indexes; measure the effect.
- Never edit posted journals, stock movements or audit events directly.

## 6. Incident and rollback

Follow the deployment and backup manuals. A rollback of application code is not a database rollback. If a migration must be reversed, stop, preserve the database, restore the verified pre-change backup into an isolated database, validate it, and obtain management approval before any production restore.

## 7. Maintenance record

| Date | Change | Approved by | Verification | Rollback tested |
| --- | --- | --- | --- | --- |
| | | | | |
