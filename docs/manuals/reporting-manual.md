# Reporting manual

## 1. Workspace

Open **Reports**. The workspace has eleven tabs:

**Executive · Financial statements · Ledger · Receivables · Payables · Procurement · Inventory · Projects · Services & equipment · Banking · Tax**

Choose **From** and **To**, then **Run report**. The report states its period and currency. Tabs your role cannot access are hidden, and the server also refuses unauthorised API calls.

## 2. Figure meanings

| Label | Meaning |
| --- | --- |
| Actual / posted | Calculated from posted journal lines only |
| Approved document | Balance from an approved invoice or document, not necessarily posted |
| Commitment | Purchase order or open commitment; not an expense |
| Estimate | Project margin or other estimate; not a posted result |
| Unavailable | Required configuration or data is missing; no value is guessed |
| Unclassified | A cash-flow counterpart lacks an approved account-role mapping |

Revenue, expenses and net result are posted ledger figures. Receivables and payables are approved document balances unless the report says otherwise. Inventory value comes from the stock ledger using the configured valuation method.

## 3. Warnings

A yellow **Data completeness warnings** panel means the affected figures are not complete. Examples:

- no chart of accounts;
- posting rules not reviewed by the Finance Controller;
- bank account not linked to a GL account;
- unapproved or missing account-role mappings;
- pending or failed financial events.

Do not remove a warning by entering a guess. Resolve the underlying configuration or report the limitation.

## 4. Tabs

- **Executive:** posted results, cash availability, document receivables/payables, inventory, projects, commitments and operational counts.
- **Financial statements:** profit or loss, balance sheet, cash flow, trial balance and period status.
- **Ledger:** general ledger for one account, with opening and closing balances.
- **Receivables / Payables:** ageing by due date. If invoices use multiple currencies, totals are shown per currency; no exchange rate is assumed.
- **Procurement:** orders by status, supplier history, outstanding deliveries, damaged/rejected quantities and document invoice values.
- **Inventory:** valuation, movements, project issues, ageing, low stock, damage and adjustments.
- **Projects:** budget, actual cost, commitments and estimated margin.
- **Services & equipment:** work orders, maintenance, utilisation, rental agreements and overdue returns.
- **Banking:** accounts, reconciliations, statements and cash accounts.
- **Tax:** approved-document VAT/WHT and the tax configuration register; not a tax remittance return.

## 5. Exports

**Export CSV (Excel)** produces a complete machine-readable export; **Export PDF** produces a printable report. PDF output is limited to the first 2,000 values and states when truncated; use CSV for the full dataset. Exports are audited and require export permission. Spreadsheet formula injection is neutralised.

## 6. Limitations

- Reporting is read-only; corrections happen in the source module.
- Report data is current when **Run report** is pressed. It does not auto-refresh after a new posting.
- Formal statements are incomplete until the chart, mappings and posting review are approved.
- Multi-currency totals are not converted.
- Very large reports take longer; narrow the date range or export CSV.
