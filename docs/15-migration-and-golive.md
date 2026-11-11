# Data Migration and Go-Live Plan (Draft)

**Version:** 0.1 — 11 November 2026
**Guide reference:** §11 (data migration and go-live procedure)
**Status:** Structure proposed. **No cut-off date, opening balance or historical scope has been decided.** Owners and inputs are UNRESOLVED pending Q-30 to Q-32.

---

## 1. What must be inventoried first (Guide §11.1)

Record for each source: what it contains, owner, date range, format, reliability, and whether it will be migrated as transactions or retained read-only.

| Source category | Typical contents | Owner | Status |
| --- | --- | --- | --- |
| Supplier and customer lists | Names, contacts, tax IDs, terms | Procurement / Sales | Not collected |
| Product/service list | Codes, descriptions, units, prices | Procurement | Not collected |
| Open purchase orders | PO number, supplier, value, received-to-date | Procurement | Not collected |
| Open GRNs / receipts not invoiced | Quantities received, awaiting invoice | Warehouse + Accounts | Not collected |
| Supplier invoices outstanding | Amount, due date, ageing | Accounts | Not collected |
| Customer invoices outstanding | Amount, due date, ageing | Accounts | Not collected |
| Payments and receipts history | Dates, references, allocations | Accounts | Not collected |
| Bank records | Statements, balances, unreconciled items | Accounts | Not collected |
| Stock register / count sheets | Item, location, quantity, condition, valuation basis | Warehouse | Not collected |
| Project registers | Codes, contracts, budgets, milestones, costs | Projects | Not collected |
| Fixed asset / equipment register | Units, ownership, location, condition | Operations | Not collected |
| Chart of accounts and trial balance | Balances per account | Accountant | Not collected |
| Employee list for user accounts | Names, roles, departments | Management | Not collected |
| Scanned document archive | Contracts, invoices, delivery notes | Various | Not collected |

## 2. Decisions required before migration work starts

| ID | Decision | Owner |
| --- | --- | --- |
| D-11 | Cut-off date and which history is imported as transactions vs kept as read-only documents | Finance + Management |
| D-11a | Whether prior-period comparative figures are loaded (and at what summarisation level) | Accountant |
| D-11b | Opening balance basis: full trial balance vs balances plus open-item schedules | Accountant |
| D-11c | Who signs off reconciliations (names, not roles) | Management |

## 3. Sequence (Guide §11.2–§11.12, adapted to this build)

1. **Agree cut-off** and the historical policy (D-11). Nothing is loaded before this is written down.
2. **Clean data:** duplicate suppliers/customers, inconsistent tax identifiers, addresses, product units, project codes and account mappings. Cleaning is a business task owned by TMD, not a build task.
3. **Physical stock count** per warehouse and location, recording quantity, condition, batch/serial where relevant and valuation basis. Signed count sheets become the migration source.
4. **Opening balances:** bank, cash, AP, AR, inventory, fixed assets, loans, equity and other accounts as applicable — prepared by the accountant.
5. **Open document schedules:** outstanding POs, GRNs, supplier invoices, customer invoices, payments, receipts and project commitments. These are needed so the first live transactions match reality.
6. **Staging load** using validated import templates: every invalid row is rejected with a reason document; **no row is silently skipped**.
7. **Reconcile** imported AP and AR to supplier/customer statements, bank balances to statements, inventory quantity and value to signed counts, and the opening trial balance to the accountant's figures.
8. **Finance and management sign-off** on the staging reconciliation. Repeat the migration after corrections if needed.
9. **Parallel run** for an agreed period: the company agrees explicitly which system is authoritative during it.
10. **Go-live approval:** lock migration snapshots, preserve originals in read-only secure storage, train users, freeze configuration changes except by change control.
11. **Post-launch monitoring:** daily exceptions, bank reconciliation, stock discrepancies, invoice posting, user access; first accounting period closed under supervision.

## 4. Migration controls (non-negotiable)

- Imports are idempotent: re-running the same file does not duplicate records.
- Every import run produces a report: rows read, accepted, rejected, and why.
- Imported opening balances post through the posting service as a controlled migration event (E-21), not by direct SQL.
- No fabricated opening balance: if the accountant cannot supply a figure, the migration for that account waits.
- Stock opening balances are recorded as movements, so the ledger tells the whole story from day one.
- Historical documents are stored read-only with their original file and a checksum.
- Production data never leaves production except into encrypted backups; staging uses synthetic or masked data.

## 5. Cutover runbook (to be completed before go-live)

| Step | Owner | Verification | Rollback |
| --- | --- | --- | --- |
| Freeze legacy edits | Management | Written notice | n/a |
| Final stock count | Warehouse | Signed count sheets | Recount |
| Final extract of open items | Finance | Totals match legacy reports | Re-extract |
| Load to production | Engineering | Reconciliation report | Restore pre-load backup |
| Reconcile and sign off | Accountant | Signed reconciliation | Correct and reload |
| Open first period | Accountant | Period status = open | Reopen legacy process |
| Train users | Management | Attendance and role checklists | Extend parallel run |
| Switch official source of truth | Management | Written authorisation | Revert to legacy for agreed period |

## 6. Training and handover (Guide §13)

Role-specific guides required: management, procurement, storekeepers, project managers, accounts, administrators. Each guide must be tested by a person in that role performing their real tasks on staging, not just read.

## 7. Go-live blockers (from Guide §16)

The release cannot proceed while any of these is failed or unrecorded:

1. Business workflows and acceptance criteria signed by department owners.
2. Role/permission matrix, maker-checker and approval limits tested and approved.
3. Accountant-approved chart of accounts, policies, tax rules and posting matrix configured.
4. Opening balances, inventory, AP, AR and bank reconciliations signed off.
5. No unbalanced or duplicate journals; reversals and period controls tested.
6. Procurement, partial delivery, GRN, invoice match, stock issue and project costing scenarios passed.
7. Invoices, credit notes, partial payments, allocations and bank reconciliation passed.
8. NRS/tax requirements and integration status validated by advisers through official channels.
9. Security review complete; critical/high findings resolved or formally accepted.
10. Access controls, audit logs, document access and sensitive-data handling verified.
11. Performance, backup, restore and DR tests complete with approved RPO/RTO.
12. Staging UAT complete with user sign-off.
13. Migration trial, reconciliation and fallback plan approved.
14. Production hosting, monitoring, support owner, escalation and rollback ready.
15. User manuals, administrator guide, deployment runbook and training complete.
16. Management has explicitly authorised go-live.

A failed item is a release blocker unless management and the relevant control owner formally record an accepted risk. Financial correctness, legal compliance, security and recoverability are not waived to meet a date.
