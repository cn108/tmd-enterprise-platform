# Managing Director acceptance script

**Participant:** Owner / Managing Director  
**System:** TMD Enterprise System, UAT environment with synthetic data only  
**Purpose:** confirm that the platform reflects how Tico McDon Limited actually intends to buy, sell, hold stock, deliver projects and approve spending.  
**Status:** **script prepared — acceptance record pending**

> Do not use real bank instructions, live customer invoices, live supplier payments, real tax IDs or production data in this session. The platform is not authorised for live financial processing.

## 1. Access and oversight (15 minutes)

| # | Step | Expected result | Result |
| --- | --- | --- | --- |
| MD-01 | Sign in with the Management test account, including MFA if prompted. | Dashboard opens with the Management focus and a visible test-environment indicator. | ☐ Pass ☐ Fail ☐ Not run |
| MD-02 | Open the module navigation. | All modules are visible; restricted modules show a limited-access indicator rather than silently disappearing. | ☐ Pass ☐ Fail ☐ Not run |
| MD-03 | Open Administration and review users and roles without changing anything. | Users and roles are readable; no create/edit control is offered. | ☐ Pass ☐ Fail ☐ Not run |
| MD-04 | Open Reports and read the completeness warnings before using a figure. | The report states its source and any missing configuration; it does not present an estimate as final. | ☐ Pass ☐ Fail ☐ Not run |

## 2. Procurement and purchasing (25 minutes)

| # | Step | Expected result | Result |
| --- | --- | --- | --- |
| MD-05 | Open the controlled request `PR-2026-0002`. | Requester is Procurement; status is approved; approver is Management and is a different person. | ☐ Pass ☐ Fail ☐ Not run |
| MD-06 | Review a purchase order and its approval band. | The order shows the required approvals for its value; the creator cannot approve their own order. | ☐ Pass ☐ Fail ☐ Not run |
| MD-07 | Review a goods receipt linked to an order. | Received quantity and rejected/damaged quantity are visible; the stock movement is traceable. | ☐ Pass ☐ Fail ☐ Not run |
| MD-08 | Try to approve a document that is already approved. | The server refuses the repeat action and preserves the original approval. | ☐ Pass ☐ Fail ☐ Not run |

## 3. Suppliers and customers (15 minutes)

| # | Step | Expected result | Result |
| --- | --- | --- | --- |
| MD-09 | Open a supplier, its contacts and bank details. | Only the last four bank-account digits are shown; the full number is not displayed. | ☐ Pass ☐ Fail ☐ Not run |
| MD-10 | Open a customer and its credit position. | Credit limit, hold status and outstanding balance are visible in the intended currency. | ☐ Pass ☐ Fail ☐ Not run |
| MD-11 | Review a customer statement/receipt. | Statement lines reconcile to approved invoices and the recorded receipt. | ☐ Pass ☐ Fail ☐ Not run |

## 4. Invoices and payments (25 minutes)

| # | Step | Expected result | Result |
| --- | --- | --- | --- |
| MD-12 | Open a customer invoice and a supplier invoice. | Test documents are clearly marked; approval and posting actions are permission-controlled. | ☐ Pass ☐ Fail ☐ Not run |
| MD-13 | Review a recorded supplier payment. | Status is recorded, not executed; allocation and remaining balance are visible. | ☐ Pass ☐ Fail ☐ Not run |
| MD-14 | Review the production gates. | Invoice test mode is on, issuance is not activated and NRS is off. | ☐ Pass ☐ Fail ☐ Not run |
| MD-15 | Review a payment/receipt reversal or cancellation. | A reason is required and the affected balances are restored; posted reversals create a controlled journal. | ☐ Pass ☐ Fail ☐ Not run |

## 5. Inventory and projects (20 minutes)

| # | Step | Expected result | Result |
| --- | --- | --- | --- |
| MD-16 | Open Inventory and review stock on hand and valuation. | Quantity, location and value are shown; no negative stock is present. | ☐ Pass ☐ Fail ☐ Not run |
| MD-17 | Open a project dashboard. | Budget, actual cost, commitments and margin are distinguished; estimates are not labelled as posted revenue. | ☐ Pass ☐ Fail ☐ Not run |
| MD-18 | Review a project material issue. | The issue is traceable to the project and stock movement. | ☐ Pass ☐ Fail ☐ Not run |
| MD-19 | Open Equipment/Leasing and review an agreement. | Equipment status, hire period, dispatch/return and inspection are visible. | ☐ Pass ☐ Fail ☐ Not run |

## 6. Approvals and financial reports (20 minutes)

| # | Step | Expected result | Result |
| --- | --- | --- | --- |
| MD-20 | Review the approval policy and delegation list. | The bands and named delegates match the intended company policy; provisional values are identified. | ☐ Pass ☐ Fail ☐ Not run |
| MD-21 | Run the trial balance and financial statements for a closed/open period. | Debits equal credits; figures come from posted journals; incomplete mapping is flagged. | ☐ Pass ☐ Fail ☐ Not run |
| MD-22 | Run receivables and payables ageing. | Balances agree to approved invoices and show the ageing buckets. | ☐ Pass ☐ Fail ☐ Not run |
| MD-23 | Review the audit trail for one approval and one reversal. | Actor, time, action and reason are recorded; the record cannot be edited. | ☐ Pass ☐ Fail ☐ Not run |

## 7. Acceptance decision

| Question | Answer |
| --- | --- |
| Do the procurement and purchasing workflows reflect TMD's intended operations? | ☐ Yes ☐ No ☐ With changes |
| Are supplier/customer, invoice and payment workflows acceptable for controlled use? | ☐ Yes ☐ No ☐ With changes |
| Are inventory, projects and equipment workflows acceptable? | ☐ Yes ☐ No ☐ With changes |
| Are the approval bands and delegation model approved? | ☐ Yes ☐ No ☐ With changes |
| Are the financial reports understandable and honestly labelled? | ☐ Yes ☐ No ☐ With changes |
| Is the role matrix (including no separate General Requester) approved? | ☐ Yes ☐ No ☐ With changes |

**Changes required:**

______________________________________________________________________________

**Business acceptance:** ☐ Accepted for production preparation ☐ Accepted with conditions ☐ Not accepted

| Field | Entry |
| --- | --- |
| Name | ________________________________ |
| Role | Owner / Managing Director |
| Date | ________________________________ |
| Signature | ________________________________ |

**Important:** this acceptance concerns business workflows. It does **not** authorise live invoicing, financial posting, bank execution, NRS submission or production go-live. Those require the separate production readiness and launch authorisations.
