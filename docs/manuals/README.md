# TMD manuals

**Version:** 12 November 2026
**System:** Tico McDon Limited enterprise platform (Angular + Django REST)
**Status:** suitable for development, UAT and training. Production financial activation and NRS submission remain blocked pending the approvals in `docs/reports/phase-7b-activation-blockers.md`.

## Manual set

| Audience | Manual |
| --- | --- |
| All employees | [Employee user manual](employee-user-manual.md) |
| System administrators | [Administrator manual](administrator-manual.md) |
| Procurement | [Procurement manual](procurement-manual.md) |
| Stores and warehouse | [Warehouse manual](warehouse-manual.md) |
| Accounts and finance | [Finance manual](finance-manual.md) |
| Project managers | [Project management manual](project-management-manual.md) |
| Treasury and bank reconciliation | [Banking manual](banking-manual.md) |
| Management and report users | [Reporting manual](reporting-manual.md) |
| Engineering / operations | [Deployment manual](deployment-manual.md) |
| Operations and support | [Backup and restoration manual](backup-restoration-manual.md) |
| Support desk | [Troubleshooting guide](troubleshooting-guide.md) |
| Technical staff | [System architecture](system-architecture.md) |
| Integrators | [API documentation](api-documentation.md) |

## Safety rules

1. Never enter invented financial figures, account mappings, tax rates or approval authority.
2. Production invoice issuance, ledger posting of live invoices, bank transfer execution and NRS submission are disabled until written activation approval.
3. Deactivate master data; do not delete it. Posted accounting records are immutable.
4. Use synthetic or masked data outside production. Never copy production records into development.
5. Report suspected financial, security or data-loss defects immediately and preserve evidence.

## Evidence and related documents

- Phase 10: `docs/reports/phase-10-reporting-completion-report.md`
- Phase 11: `docs/reports/phase-11-production-readiness-report.md`
- Full audit: `docs/reports/full-system-acceptance-report.md`
- Migration plan: `docs/15-migration-and-golive.md`
- Migration templates: `docs/templates/migration/`
- Activation blockers: `docs/reports/phase-7b-activation-blockers.md`
