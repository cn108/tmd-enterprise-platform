# Procurement manual

## 1. Scope

Procurement covers purchase requests, requests for quotation, supplier quotations, supplier selection, purchase orders, delivery schedules and goods receipts. Supplier invoices and payments are handled in the Invoices module.

## 2. Standard flow

1. **Purchase request** — requester states destination, department, required date, justification and lines.
2. **Approval** — an authorised approver submits/approves according to the approval policy. Self-approval is blocked.
3. **RFQ** — invite suppliers and record quotations.
4. **Supplier selection** — record the selected quotation and reason.
5. **Purchase order** — issue the approved order. The order value is a **commitment**, not an expense.
6. **Delivery schedule** — record expected quantities and dates.
7. **Goods receipt** — Stores records delivered, accepted, rejected and damaged quantities. Stock enters the inventory ledger only through the receipt.
8. **Supplier invoice** — Accounts records and matches the invoice to the order and receipt.

## 3. Status discipline

Use the status shown by the server. Do not manually force a later status. Invalid transitions return a conflict and leave the record unchanged. Cancel rather than delete. A cancelled order remains visible for audit.

## 4. Partial deliveries

Record each delivery separately against the schedule. The outstanding quantity is the ordered quantity less delivered quantity. A purchase order becomes partially received until all lines are complete.

## 5. Supplier performance

The procurement report shows order counts, order values, period invoice values, outstanding deliveries and recorded lead times. Treat lead time as missing when no quotation recorded it; do not infer a value.

## 6. Financial meaning

- Purchase request: no commitment.
- Approved/issued purchase order: commitment.
- Goods receipt: stock movement and, where configured, a GRNI accrual event.
- Approved supplier invoice: recorded payable document; it becomes an actual ledger expense only after posting.
- Payment: settlement, not a second expense.

Never describe a purchase order total as expenditure. The reporting workspace labels commitments separately.

## 7. Controls

- Check supplier identity, tax registration and bank details before first use.
- A change to supplier bank details follows the bank-change control; do not edit bank details silently on a live supplier.
- Attach quotations, delivery notes and other evidence to the relevant record.
- Reconcile the purchase order, receipt and invoice before approving payment.
- Record the reason for any duplicate override or matching exemption.

## 8. Reports

Open **Reports → Procurement** for purchase orders by status, supplier history, outstanding deliveries, damaged/rejected quantities and document invoice values. Use the date filters. Export only if your role permits it.
