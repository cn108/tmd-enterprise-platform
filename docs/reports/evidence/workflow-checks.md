# End-to-end workflow evidence

All workflows passed: **True**

| Workflow | Result | Evidence |
| --- | --- | --- |
| A_procurement_to_inventory | PASS | request=PR-2026-0001; order=PO-2026-0001; goods_receipt=GRN-2026-0001; receipt=RCP-2026-0001 |
| B_procurement_to_supplier_invoice | PASS | invoice=SI-2026-0001; match_status=matched; total=680000.00 |
| C_customer_delivery_to_receivables | PASS | invoice=CI-2026-0001; balance=2500000.00 |
| D_payment_to_bank_reconciliation | PASS | payment=PAY-2026-0001; payment_status=recorded; execution=recorded; reconciliation=REC-2026-0001 |
| E_inventory_allocation_to_project_cost | PASS | issue=ISS-2026-0001; project=PRJ-STG-001; issue_value=240000.00 |
| F_project_budget_to_expenditure | PASS | budget=1; budget_status=approved; actual_cost=300000.00 |
| G_equipment_rental_lifecycle | PASS | agreement=RA-2026-0001; agreement_status=closed; movements=2; inspection_damage=False; maintenance=planned |
| H_accounting_to_management_reporting | PASS | journals=11; net_result=2485000.00; trial_balanced=True |
| partial_and_damaged_delivery_handled | PASS | damaged=1.0000; rejected=0.0000; reason=UAT: one pump damaged in transit. |
| service_contract_to_customer_acceptance | PASS | contract=SC-2026-0001; work_order=WO-2026-0001; status=accepted |
