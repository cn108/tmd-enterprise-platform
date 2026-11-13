# Migration template validation

**Result:** PASS
**Templates:** 15 files, 17 data rows
**Errors:** 0
**Warnings:** 0

This report validates template structure, data types, cross-file references,
duplicates and invoice/trial-balance arithmetic. It does not import records,
approve account mappings, verify source documents or authorise opening balances.

## Row counts

| Template | Rows |
| --- | ---: |
| company_profile.csv | 1 |
| employees.csv | 1 |
| suppliers.csv | 1 |
| customers.csv | 1 |
| projects.csv | 1 |
| products.csv | 1 |
| warehouses.csv | 1 |
| equipment.csv | 1 |
| inventory_balances.csv | 1 |
| supplier_invoices.csv | 1 |
| customer_invoices.csv | 1 |
| bank_balances.csv | 1 |
| opening_trial_balance.csv | 2 |
| commitments.csv | 1 |
| advances.csv | 2 |

## Errors

None.

## Warnings

None.

## Boundary

A PASS is a pre-import structural result only. Trial import into staging,
source-document reconciliation and written Finance/Management approval remain
mandatory before production.
