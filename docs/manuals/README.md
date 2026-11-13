# TMD manuals

**Version:** 13 November 2026
**System:** Tico McDon Limited enterprise platform (Angular + Django REST)
**Status:** technically complete for controlled UAT and training; production deployment, financial activation and NRS submission remain blocked pending the approvals in `docs/reports/final-production-readiness-report.md`.

## Manual set

| Audience | Manual |
| --- | --- |
| Owner / Managing Director | [Owner and Managing Director manual](owner-managing-director-manual.md) |
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
| Technical staff / operations | [Maintenance procedures](maintenance-procedures.md) |
| Management / operations | [30-day post-launch monitoring plan](post-launch-monitoring-plan.md) |

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
