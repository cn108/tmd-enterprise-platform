# Warehouse and inventory manual

## 1. Principles

The stock movement ledger is the source of truth. Balances are derived from movements, not typed over. Never edit a posted movement; use a return, adjustment or count correction with a reason.

## 2. Receipts

1. Open the goods receipt linked to the purchase order and delivery schedule.
2. Record delivered, accepted, rejected and damaged quantities.
3. Give a reason for every rejection or damage.
4. Confirm the receipt. Accepted stock is posted to the warehouse.
5. File the supplier delivery note as a supporting document.

Do not accept more than the outstanding quantity without an authorised order amendment.

## 3. Transfers

Record the source warehouse, destination, lines and quantities. A transfer must not create a second purchase cost. The same stock moves; it is not received again.

## 4. Issues to projects

Issue stock against the correct project and cost centre. The issue reduces inventory and contributes to project actual cost. A project issue is not a new purchase.

## 5. Returns

Return unused stock through **Returns**, recording the project or source. Return-to-supplier is recorded against the original receipt and follows the procurement correction process.

## 6. Adjustments, damage and counts

- **Adjustment:** correct a book error with a reason and authorisation.
- **Damaged stock:** record the damage and disposal/write-off evidence.
- **Stock count:** record counted versus system quantity. Variances are posted as adjustments with a reason; do not overwrite the balance.
- Negative stock is not a valid correction. Investigate the missing receipt or issue.

## 7. Reservations and reorder levels

Reservations protect stock for approved demand but do not move stock. Reorder alerts use recorded reorder levels. A low-stock alert is a signal, not an automatic purchase order.

## 8. Valuation

Inventory value uses the approved valuation policy. If no policy is configured, valuation is unavailable and the UI says so. Do not estimate a value in a report.

## 9. Reports

**Reports → Inventory** shows balances, movements, project issues, ageing, low stock, damage and warehouse activity. The ageing date is the report end date. Exports are audited.

## 10. Period checks

At each month end, reconcile physical stock, movement ledger and valuation; investigate every negative balance, unexplained adjustment and unmatched receipt.
