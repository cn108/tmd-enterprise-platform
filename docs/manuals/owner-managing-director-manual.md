# Owner / Managing Director manual

## 1. Your role

You are the business owner and final approval authority. The platform records your decisions; it does not replace them. You do not need to hold every operational role, but you must name who holds each role and who can approve what.

Technical administrator access is separate from financial authority. A System Administrator can configure the system but must not approve a payment, invoice, journal or period close unless separately granted that business role.

## 2. What you can do in the platform

- Review the dashboard, procurement pipeline, project position, inventory value and financial reports according to your assigned role.
- Approve purchase requests, orders, budgets, journals, invoices and other documents where your role and the approval band permit.
- Read administration lists for oversight; Management and Auditor are read-only in user administration.
- Review audit events, configuration completeness warnings and production gates.
- Open reports only when the underlying data is complete; a warning means a figure is not final.

## 3. Decisions only you or your delegate can make

| Decision | Why it cannot be automated | Record |
| --- | --- | --- |
| Role holders and delegated authority | The platform has ten roles, but people must be named | Access review / role matrix |
| Approval thresholds | A monetary band is company policy | Approval policy record |
| Chart of accounts and posting rules | Accounting policy requires professional review | Finance configuration sign-off |
| VAT, WHT, tax IDs and NRS onboarding | Statutory positions must be verified | Tax adviser opinion |
| Opening balances | Must reconcile to bank, supplier, customer and stock records | Signed opening trial balance |
| Go-live and financial activation | Business risk decision | Written launch authorisation |
| Production hosting, domain and backup ownership | Operational accountability | Infrastructure handover |

## 4. Monthly operating rhythm

1. **Week 1:** review the previous month's bank reconciliations, supplier statements and customer ageing.
2. **Before month-end:** ensure all receipts, invoices, payments and stock movements are recorded and approved; do not leave draft documents unresolved.
3. **Month-end:** the Finance Controller or accountant closes the period only after the trial balance and control accounts reconcile.
4. **Review:** compare actual results with the prior month, investigate large or unusual items, and record decisions.
5. **Backup/restore:** confirm the backup monitoring result and that a restore test is current.

The first month-end close is an acceptance criterion for the project, not a formality.

## 5. What not to do

- Do not approve your own transaction where independent approval is required.
- Do not ask an administrator to change a posted journal or delete an audit record.
- Do not use test invoices, test payments or synthetic data as company records.
- Do not authorise live invoicing, bank execution or NRS submission until the production readiness report says the gate is closed.
- Do not share your password, MFA code or recovery codes.

## 6. Escalation

| Issue | First contact | Preserve |
| --- | --- | --- |
| Suspected fraud or unauthorised payment | Management and Finance Controller | Audit log, bank records, request IDs |
| Wrong ledger balance | Finance Controller / accountant | Journal, source document, period status |
| System outage or data loss | Software Administrator | Time, error message, last known transaction |
| Suspected data breach | Software Administrator and Management | Logs, affected accounts, notification timeline |
| Lost MFA device | Software Administrator | Identity verification record |

## 7. Sign-off

| Item | Name | Date | Signature |
| --- | --- | --- | --- |
| Business workflows accepted | | | |
| Role matrix and delegates approved | | | |
| Go-live authorisation | | | |
| First month-end close accepted | | | |
