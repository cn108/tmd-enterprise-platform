## Phase: 6 — Financial accounting engine (backend APIs)

**Date:** 11 November 2026
**Prepared by:** Build agent, for review by TMD management and the technical owner
**Status:** ready for review — **partial phase report.** The double-entry engine, approval workflow, periods, closing and reports are implemented and tested; no chart of accounts or posting rules are supplied or accountant-approved, and no screens, database-level immutability or multi-currency support exist. The Phase 6 exit gate is **not** met.

### Requirements addressed

`GL-01` chart of accounts as configuration with explicit approval, `GL-03` balanced journals with at least two lines, `GL-04` one central journal-creation service, `GL-06` posted journals protected from API edits with linked reversals, `GL-07` idempotent event posting, `GL-08` trial balance, general ledger, income statement and balance sheet, `GL-09` configured and approved posting rules, and `GL-11` controlled opening balances.

**Partially addressed:** `GL-02` supports open and closed periods and rejects posting into a closed period, but has no soft-close/locked states and no reopen workflow. `GL-05` records the source type, posting rule, event reference and project/cost-centre/party dimensions, but not a generic source-document type and ID for every manual journal. `GL-06` immutability is enforced at the API (no update or delete route) and by the service workflow, not by a database trigger. `GL-11` provides document-based opening balances with a single posting per fiscal year, but no file import, row rejection report or sign-off/reconciliation workflow.

**Not addressed:** `GL-10` multi-currency and revaluation (Q-25; the engine is NGN only), period reopening, database-level append-only triggers, automated posting adapters from procurement, inventory, projects, invoicing, payments or assets, and financial statement layouts for statutory filing.

### Implemented

- **Chart of accounts (GL-01).** Accounts carry a client-supplied code, name, type (asset, liability, equity, income, expense), normal balance, optional parent, active flag and an approval by a **different** user holding `accounting.approve_account`. No account is seeded. Deletion is refused; accounts are deactivated. Posting refuses any account that is inactive or unapproved.
- **Fiscal years and periods (GL-02).** Fiscal years and periods are client data with no defaults. A period must fall inside its fiscal year and cannot overlap another period in the same year. Periods are `open` or `closed`; posting into a closed period is refused. There is no automatic reopening.
- **Journals (GL-03, GL-04).** A journal has at least two lines, each with exactly one of debit or credit, non-negative amounts and equal totals. Money is `NUMERIC(18,2)`. Every creation path — manual, adjustment, opening balance, reversal, period close and configured event — goes through the same `_create_journal` service. Lines can carry project, cost centre, party and item dimensions.
- **Approval workflow.** Draft → submitted → approved → posted. Approval requires `accounting.approve_journal`; the creator cannot approve their own journal. Posting requires `accounting.post_journal`, an approved journal, an open period, approved active accounts and a revalidated balance. Totals are snapshotted at posting.
- **Adjustments.** A manual journal can be marked an adjustment; a reason is mandatory and is stored with the journal.
- **Reversals (GL-06).** A posted journal can be reversed once by a user with `accounting.reverse_journal` and a mandatory reason. The reversal is a new posted journal with every debit and credit swapped, linked through `reversal_of`, and may target a different open period. The original remains posted and unedited. A reversal cannot itself be reversed; a further correction must be an adjustment.
- **Opening balances (GL-11).** One opening-balance document per fiscal year (`OB-`), with balanced debit/credit lines and optional project/cost-centre dimensions. Posting creates and posts a journal (`JV-`); the document and journal are linked. A draft can be entered unbalanced; posting refuses it until it balances.
- **Posting rules (GL-09).** A rule maps named amount keys to debit/credit accounts. Rules require approval by a different user with `accounting.approve_postingrule`, and every account on the rule must already be approved. The event endpoint takes a rule, date, open period, description, amounts keyed to the rule, an optional reference and project/cost-centre/party dimensions. It refuses unknown or missing keys, negative amounts, an unbalanced result, an inactive or unapproved rule, and a duplicate `(rule, reference)` pair. This is the integration path for procurement, inventory, projects, invoicing, payments and asset events; no account is hard-coded in any module.
- **Period closing.** Closing is refused while the period contains a journal that is not posted or a draft opening balance. It requires a configured retained-earnings account that is approved, active and of type equity. Income and expense balances are zeroed by a posted closing journal and the difference is posted to retained earnings; the period is then marked closed with who and when. No result means no closing journal is required.
- **Reports (GL-08).** Trial balance by period or as-of date with debit/credit totals and a `balanced` flag; general ledger detail for an account with an opening balance, running balance and closing balance; income statement over a date range (closing entries excluded so the period's result remains visible); balance sheet as of a date with assets, liabilities, equity, the unclosed result and a balance check.
- **Configuration.** The only accounting configuration outside accounts and rules is the retained-earnings account, set through `accounting.configure_accounting` and validated as an approved, active equity account.
- **Numbering.** Journals use `JV-YYYY-NNNN` and opening balances `OB-YYYY-NNNN` from the shared locked sequence. No manual number is accepted.
- **Permissions.** `manage_accounts`, `approve_account`, `manage_fiscalyears`, `manage_periods`, `close_period`, `create_journal`, `approve_journal`, `post_journal`, `reverse_journal`, `manage_openingbalance`, `manage_postingrules`, `approve_postingrule` and `configure_accounting`. They are data, so W4 can map them to roles without code changes.

### Deliberately not included

- **Chart of accounts and posting rules.** The build team has not supplied any account, code, mapping or retained-earnings entry. D-05/Q-22 requires the accountant's chart and posting matrix; the engine refuses to post against unapproved records until then.
- **Screens.** No accounting page exists in the Angular portal; the API is the only surface.
- **Roles and record visibility.** W4/W5 remain blocked by D-03/D-17; the permissions must be granted by hand.
- **Database-level immutability.** Posted journals cannot be changed through the API, but a database trigger preventing ORM updates is not installed (W7 audit remains blocked).
- **Multi-currency and revaluation.** NGN only; Q-25 is unresolved.
- **Period reopening and soft-close/locked states.** A closed period stays closed; correction journals must be posted in an open period.
- **Generic source-document links and automatic module posting.** Events carry a posting rule and reference, but there is no automatic call from Phase 4/5 documents yet, because the accounts and rules they would use must first be approved.
- **Statutory statement layouts, tax and consolidated reporting.** Out of scope until the accounting policies are signed.

### Files/modules changed

- New app `backend/apps/accounting/`: `models.py` (accounts, fiscal years, periods, journals and lines, opening balances, posting rules, settings), `services.py`, `serializers.py`, `views.py`, `urls.py`, `numbering.py`, `apps.py`, migration `0001_initial.py`.
- `backend/apps/accounting/tests/test_accounting.py`: 29 tests.
- `backend/config/settings/base.py`: `apps.accounting` registered.
- `backend/config/urls.py`: accounting router mounted under `/api/v1/`.
- Documentation: this report, `README.md`, `14-backlog.md`, `13-decision-register.md` (B-40…B-46).

### Database changes

One new app with one initial migration creating ten tables and their constraints (one debit/credit side per line, non-negative amounts, unique line numbers, one opening balance per fiscal year, unique event reference per posting rule, unique period name per fiscal year). No existing table changed. `makemigrations --check` reports no pending changes. Nothing is seeded: no account, fiscal year, period, rule, opening balance or retained-earnings mapping.

### Tests run

| Command | Result |
| --- | --- |
| `pytest` (backend) | **180 passed**, exit 0 — 151 existing + 29 new accounting tests |
| `ruff check .` | All checks passed, exit 0 |
| `ruff format --check .` | All files formatted, exit 0 |
| `python manage.py check` | No issues, exit 0 (1 silenced: `axes.W002`) |
| `python manage.py makemigrations --check --dry-run` | No changes detected, exit 0 |

What the tests assert, beyond executing: no accounts are seeded; account codes are normalised; approval needs the permission and a different user; unbalanced journals and lines with both sides are refused before creation; a balanced journal flows through submit, approve and post with totals; the creator cannot approve their own journal; an unapproved account blocks posting; posted journals have no update or delete route; an adjustment journal requires a reason; journal dates must fall inside their period; trial balance totals reconcile and filter by period; the general ledger runs a closing balance; reversal posts opposite entries and cannot happen twice; a reversal in a closed period requires an open target period; an opening balance posts once, enters the trial balance and cannot be posted again; an unbalanced opening balance is refused; closing zeroes income and expense into retained earnings, marks the period closed, blocks later journals and keeps the balance sheet balanced; closing requires retained earnings when there is a result; an unposted journal blocks closing; overlapping periods are refused; the income statement and balance sheet reconcile; posting-rule events post balanced, dimensioned journals; unapproved rules, unknown or missing amount keys, unbalanced amounts and duplicate references are refused; rule approval requires permission and a second user; retained earnings must be an approved equity account.

### Acceptance evidence

- **Automated:** the commands above, against the live PostgreSQL instance.
- **Runtime smoke test:** anonymous `/api/v1/accounts/`, `/api/v1/fiscal-years/`, `/api/v1/accounting-periods/`, `/api/v1/journals/`, `/api/v1/opening-balances/`, `/api/v1/posting-rules/`, `/api/v1/accounting-settings/`, `/api/v1/trial-balance/`, `/api/v1/financial-statements/` and `/api/v1/general-ledger/` → `401`; `/api/v1/schema/` lists all ten routes; `/health/` → `200`.
- **Not evidenced:** browser screens (none exist), a real accountant-approved chart or posting matrix (not supplied), multi-currency, database-level append-only enforcement, and automatic posting from Phase 4/5 documents.

### Unresolved decisions

| ID | Decision | Owner | Impact if unanswered |
| --- | --- | --- | --- |
| D-05 / Q-22 | Chart of accounts, financial year and posting matrix | Accountant | No real account or rule can be loaded; the engine is complete but empty |
| D-04 | Approval limits and maker-checker | Management + Finance | Journal approval needs a permission and a different user, but no value thresholds or delegation |
| D-03 / D-17 | Roles and record visibility | Management | Accounting permissions must be granted by hand; every signed-in user can read all journals and reports |
| D-23 | Rounding policy | Accountant | Money is rounded to two decimal places per line; no per-document rounding rule exists |
| Q-25 | FX policy | Accountant | NGN only; multi-currency and revaluation are disabled |
| D-08 | Document numbering | Accountant | Internal `JV-`/`OB-` numbers are used; external document numbering is not implemented |
| W7 | Append-only audit trail | Management | Posted journals are API-immutable but not protected by a database trigger |

### Risks and limitations

| Risk | Severity | Mitigation / workaround |
| --- | --- | --- |
| No accountant-approved chart, rules or retained-earnings mapping | High | Nothing is seeded; accounts and rules require approval and posting refuses unapproved records. Production use is blocked until D-05/Q-22 is signed |
| Permissions are assigned by hand | High | They are data; W4 can map them to roles. Until then a superuser grants them |
| API-level immutability is not a database guarantee | High | No journal update/delete routes exist; a database trigger is needed for W7 and production hardening |
| No automatic posting from procurement, inventory, projects, invoices, payments or assets | High | The configured event endpoint is the integration path; adapters must be added only after the posting matrix is approved |
| Closing is irreversible in this implementation | Medium | Correction journals must be posted in an open period; a reopen workflow needs an approved control |
| Multi-currency is absent | Medium | NGN-only per the confirmed reporting currency; Q-25 must be answered before enabling FX |
| Rounding is per line to two decimals | Medium | D-23 must confirm; residual differences should be posted through an adjustment |
| No source-document drill-through for manual journals | Medium | Events and reversals carry references; manual journals need a source reference convention |
| No screens: accounting is API-only | Medium | Portal work package required before finance staff can use it |
| No opening-balance import/reconciliation workflow | Medium | Opening balances are API documents; a controlled import and sign-off remain outstanding |

### Recommendation

Ready for review as a **double-entry accounting engine**, not as a production ledger. It cannot invent an account, a posting rule or a retained-earnings mapping, and posting against unapproved configuration is refused. It should not be used for company books until the accountant supplies and approves the chart of accounts and posting matrix (D-05/Q-22), W4 maps permissions to roles, W7 protects the tables at the database level, and the Phase 4/5 source adapters are added against approved mappings.

### Next phase proposal

Phase 7 (accounts payable) is the natural consumer of the engine but is blocked by D-07 (tax), D-08 (invoice numbering) and D-21. Before Phase 7, close W4/W7 and obtain the D-05/Q-22 chart and posting matrix, so supplier invoices can post to approved accounts rather than placeholders.

---

## Addendum — 11 November 2026 (session 2)

The accounting surface is now interactive: chart maintenance with separate approval, fiscal years, periods and closing, journals through submit/approve/post/reverse, opening balances, posting-rule authoring and approval, and a report workspace for trial balance, general ledger, income statement and balance sheet. A PostgreSQL trigger now makes posted journals and their lines immutable even to raw SQL; the suite proves the refusal with direct ORM writes.

Still outstanding: the accountant-approved chart and posting matrix (D-05/Q-22), W4 role assignment, multi-currency, period reopening, automatic postings from source modules, and idempotency keys. Production posting remains **BLOCKED** until those are supplied and signed. The module remains **PARTIAL**.

## Addendum — 12 November 2026 (session 3)

The provisional decisions are now configured: 19 account roles, role-based posting-rule lines, effective-dated approved mappings, monthly period generation, controlled reopen and the E-02/E-04/E-16 outbox. **No account or mapping has been supplied**, so role-based rules cannot be approved and automatic posting remains blocked. Opening balances and the Finance Controller posting review are also outstanding. The full status is in [`configuration-report-2026-11-12.md`](configuration-report-2026-11-12.md).

## Rules applied to this report

- No financial feature is reported as production-ready; none was built.
- "Implemented" means code, tests and documentation together — not a page that renders.
- No real company data, credentials or personal data appear here; all test data is synthetic.
