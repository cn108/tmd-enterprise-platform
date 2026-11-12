# Administrator manual

## 1. Responsibilities

The administrator manages users, roles, configuration and operational health. The administrator does **not** decide accounting policy, tax treatment, approval authority or opening balances. Those require the Finance Controller, tax adviser and management.

## 2. Accounts and roles

Use **Administration** to create users and assign roles. The provisional role matrix is:

- System Administrator
- Management
- Accountant
- Finance Controller
- Finance Officer
- Procurement Officer
- Project Manager
- Storekeeper
- Operations / HSE
- Auditor

Rules:

1. Give each person their own account. Never share credentials.
2. Grant the minimum role needed. Use the access review screen to inspect effective permissions.
3. Remove access promptly when a person leaves or changes duties.
4. A user cannot approve their own restricted transaction.
5. Assign at least one independent approver before testing approval workflows.

Role changes and sensitive configuration changes are audited.

## 3. Activation gates

The following remain disabled until the blockers in `docs/reports/phase-7b-activation-blockers.md` are evidenced:

- live customer invoice issuance;
- posting of live invoice journals;
- bank transfer execution;
- NRS submission;
- production financial activation.

Do not set `InvoiceSettings.test_mode` to false or populate activation fields merely to make a test pass. Activation is a dated management decision.

## 4. Configuration

- **Chart of accounts:** approve accounts before mapping roles.
- **Account-role mappings:** every required role needs an approved, effective mapping. Reporting warns when mapping is missing.
- **Tax configuration:** review every rate and effective date with the tax adviser.
- **Numbering:** customer-invoice numbering must be reviewed before activation.
- **Approval policies:** thresholds are provisional until management approves them.
- **Inventory policy:** valuation method must be approved by finance.

## 5. Sessions and security

- Absolute session timeout: 12 hours; inactivity cookie age: 1 hour.
- Failed sign-ins are rate-limited and lock out by username and IP.
- Production requires HTTPS, secure cookies, HSTS and a private database.
- Secrets belong in the deployment secret store, never in source code, chat or screenshots.
- Review audit logs for unusual approvals, exports, downloads and permission changes.

## 6. Backups and restores

Backups are run by the operations owner using `scripts/backup.sh`. A restore must be tested into an isolated database with `scripts/restore.sh`; never restore over production to "check" a backup. See the [Backup and restoration manual](backup-restoration-manual.md).

## 7. Deployment and health

Use the [Deployment manual](deployment-manual.md). Check `/health/` and `/health/ready/`, application logs, disk capacity and database capacity. The current build does not include a production monitoring/alerting integration; that is an identified blocker.

## 8. Incident handling

1. Preserve logs and audit records.
2. Stop the affected process if it is writing incorrect financial data.
3. Do not delete records to hide an error.
4. Record the time, users, records and request identifiers.
5. Escalate financial integrity issues to the Finance Controller and security issues to management.
6. Restore only from a verified backup and reconcile after recovery.

## 9. What not to do

- Do not run destructive SQL, reset the database, or delete migrations.
- Do not disable permissions or tests to clear an error.
- Do not copy production data into development.
- Do not commit `.env`, keys, certificates or backups.
