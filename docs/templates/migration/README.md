# Migration templates

These CSV files define the controlled import format for a staging trial. The example rows are **synthetic** and must be replaced. No importer is enabled in this release; a clean validation is not an approval to load production.

## Files

| File | Purpose | Key references |
| --- | --- | --- |
| `company_profile.csv` | Legal name, RC/TIN/VAT numbers, registered address, year end and reporting currency | exactly one row |
| `employees.csv` | User identity, role, department, active and MFA-required flags | unique `email`; role names from the approved matrix |
| `suppliers.csv` | Supplier master data | unique `code` |
| `customers.csv` | Customer master data | unique `code` |
| `projects.csv` | Projects and approved budget totals | `customer_code` |
| `products.csv` | Products and services | `uom_code`, `category_code` must exist in the approved catalogue |
| `warehouses.csv` | Warehouse locations | unique `code` |
| `equipment.csv` | Owned or leased equipment and assets | unique `code` |
| `inventory_balances.csv` | Opening stock quantities and unit costs | `warehouse_code`, `item_code` |
| `supplier_invoices.csv` | Outstanding supplier invoices | `supplier_code` |
| `customer_invoices.csv` | Outstanding customer invoices | `customer_code`, optional `project_code` |
| `bank_balances.csv` | Opening bank statement balances | existing company bank account code |
| `opening_trial_balance.csv` | Account-level opening debit/credit | approved `account_code` |
| `commitments.csv` | Outstanding purchase commitments | `supplier_code` |
| `advances.csv` | Supplier and customer advances | `party_type` + `party_code`; unique reference per party |

## Rules

1. Save as UTF-8 CSV with the exact header order.
2. Use ISO dates (`YYYY-MM-DD`) and dot decimals (`1234.50`).
3. Do not add totals, blank spacer rows or formula cells.
4. Invoice `total` must equal `subtotal + vat_total - wht_total`.
5. The opening trial balance must balance; each line has debit or credit, not both.
6. Do not silently drop a source row. Record rejected rows and the reason.
7. Keep the original source file, checksum and preparer name outside the CSV.

## Validate

```bash
python scripts/validate_migration.py \
  --templates docs/templates/migration \
  --report docs/reports/evidence/phase-11-migration-template-validation.md
```

The command exits non-zero on any error. Fix the source data and rerun; do not edit the validator to accept bad rows.

## Trial import gate

A staging trial requires:

- written cut-off and historical policy;
- approved chart of accounts and account-role mappings;
- signed opening trial balance;
- reconciled AP, AR, bank, inventory and commitment schedules;
- row-level reconciliation to source documents;
- Finance Controller and management sign-off.

Until those exist, migration remains a validated template exercise only. The current template validation result is `docs/reports/evidence/phase-11-migration-template-validation.md`.
