# Security and Permission Test Report

**Environment:** isolated QA clone `tmd_qa_adversarial_20261113`  
**Roles:** 10  
**Role-page visits:** 120  
**Direct API checks:** 45/45 passed  
**Session/CSRF checks:** 7/7 passed  
**Critical or high security defects remaining:** 0 known

---

## 1. Access-control model

The live permission matrix was used, not older documentation. The application supports ten roles:

System Administrator, Management, Accountant, Finance Controller, Finance Officer, Procurement Officer, Project Manager, Storekeeper, Operations/HSE and Auditor.

There is no separate General Requester role. Every authenticated employee can initiate a purchase request subject to the backend's create permission and workflow rules.

Management and Auditor hold **read-only** access-administration grants. This is intentional: their `GET /access/users/` and `/access/roles/` return 200, while write attempts return 403. This was verified both in the role matrix and by direct probe (`management_cannot_create_users` → 403, `finance_cannot_write_access_roles` → 403).

## 2. Workspace restrictions

| Role | Restricted workspaces in the browser |
|---|---|
| System Administrator | None |
| Management | None |
| Accountant | Administration |
| Finance Controller | Administration |
| Finance Officer | Administration |
| Procurement Officer | Banking, Administration |
| Project Manager | Banking, Administration |
| Storekeeper | Banking, Administration |
| Operations / HSE | Invoices, Banking, Administration |
| Auditor | None |

The restricted page renders an Access Restricted panel and removes record rows and write controls. It does not silently show empty data as if the user had access.

Five console messages remain across Procurement, Project, Store and Operations: the browser reports the backend's correct 403 for the restricted list request before the panel renders. No restricted rows, totals or documents are exposed. This is recorded as a low-severity UX noise issue, not a permission bypass.

## 3. Direct API matrix

| Endpoint | Allowed 200 | Denied 403 |
|---|---:|---:|
| `/access/users/` | Admin, Management, Auditor (3) | 7 roles |
| `/access/roles/` | Admin, Management, Auditor (3) | 7 roles |
| `/company-bank-accounts/` | 6 roles | Procurement, Project, Store, Operations |
| `/supplier-invoices/` | 9 roles | Operations |
| `/customer-invoices/` | 9 roles | Operations |
| `/purchase-orders/` | 10 roles | — |
| `/stock-movements/` | 10 roles | — |
| `/equipment/` | 10 roles | — |
| `/accounting-settings/` | 10 roles | — |
| `/trial-balance/` | 0 | 0 (all returned 400 for missing dates) |

`/trial-balance/` returning 400 in all ten roles is a required-parameter response, not a permission denial. It was not treated as a security finding.

## 4. Object-level and method-level checks

| Attempt | Result |
|---|---|
| Operations reads an existing-format invoice id it does not own/access | 403 |
| Operations requests a customer-invoice PDF | 403 |
| Anonymous requests the invoice list | 401 |
| Administrator requests a missing object | 404 |
| Operations requests the same missing object | 403 (does not confirm existence) |
| Auditor creates a supplier | 403 |
| Management creates a supplier | 403 |
| Management creates a user | 403 |
| Finance Officer creates a role | 403 |
| Procurement reads access users | 403 |
| Operations reads company bank accounts | 403 |

The difference between the administrator's 404 and the unauthorised role's 403 reduces object-existence leakage.

## 5. Segregation of duties

The backend, not the UI, enforces:

- creator ≠ approver for invoices, receipts, journals and reconciliations;
- two distinct approvers for high-value invoices;
- no edit after supplier-invoice approval;
- no repeat submit/approve/post;
- no receipt of goods against a closed order;
- no closure of an already-closed period;
- no over-allocation or cross-customer receipt allocation;
- no dispatch of a closed rental agreement.

All of these returned 400/403/409 with no state change. Details are in the [invalid input report](invalid-input-and-validation-report.md) and [cross-module report](cross-module-workflow-test-report.md).

## 6. CSRF and session security

Seven session checks passed:

1. CSRF bootstrap returned 200.
2. Login returned 200.
3. Login set a `sessionid` cookie marked **HttpOnly**.
4. Authenticated `/me` returned 200.
5. A mutation without an `X-CSRFToken` header returned 403.
6. A mutation with a foreign `Origin` returned 403.
7. Logout returned 204 and the next `/me` returned 401.

The session cookie is not exposed to JavaScript by the application. The test did not wait for the configured idle timeout, so absolute/idle expiry is not claimed as exercised; logout invalidation is proven.

## 7. Injection and hostile content

- A supplier legal name containing `<script>window.__qaXss=1</script>` and a note containing an `onerror` image payload were stored through the real form. The list and detail rendered the text literally; no script ran and `window.__qaXss` stayed undefined.
- A search string `' OR 1=1 --` returned 200 with zero matches; the SQL-like text did not broaden the result set or produce a 500.
- The QA fixtures `QA-XSS-001` and `QA-SQL-001` remained intact and did not affect the party table.
- The backend uses bound ORM queries; no raw SQL path was found in the tested endpoints.

## 8. File upload security

A real `.exe` upload was attempted through the document form. The backend rejected it with 400 and returned the allowed-extension list; the UI displayed that message. The failed request did not create a document. File bytes are private, downloads are authenticated, and no public media URL was observed.

Not exercised in this pass: oversized file, corrupted PDF/XLSX, mismatched MIME type, duplicate attachment, unusual filename characters. The serializer has explicit extension and size checks, but those additional cases remain a coverage gap.

## 9. Error and log exposure

- API errors use the standard `{error: {code, message, details, request_id}}` envelope.
- No password, secret or full bank account number appeared in the tested UI responses.
- Bank-account serializers expose only `account_last4`, not the full number.
- The QA API log records request paths and status codes; it does not contain the role password.
- No stack trace or SQL statement was shown to the browser during the probes; rejected requests returned controlled 400/403/409 envelopes.

## 10. Privilege-escalation attempts

The following were refused:

- Finance Officer creating a role (403).
- Management creating a user (403).
- Auditor/Management creating a supplier (403).
- Procurement/Project/Store/Operations reading access administration (403).
- Operations reading financial invoices or bank accounts (403).
- Operations requesting a PDF (403).
- Reusing another customer's invoice in a receipt (400).

No role was able to grant itself a permission or read a restricted financial dataset through a direct URL or API call.

## 11. Security-related fixes

| ID | Finding | Security impact | Fix |
|---|---|---|---|
| TMD-ADV-01 | Party option endpoint denied everyone because the permission class could not resolve the model | Availability, not bypass: legitimate party lookups failed; could push users toward workarounds | Added queryset; permission still enforced for users without `view_party` |
| TMD-ADV-05 | RFQ invitation detail route missing | Broken access path, not a bypass | Added retrieve under the existing view permission |
| TMD-ADV-06 | Computed report View called nonexistent detail routes | Broken UI, not a bypass | Open the already-authorised row detail locally |

No critical or high-severity security vulnerability was found after the fixes.

## 12. Limitations

- No penetration test of the host, TLS terminator, proxy or database was performed; this was application-level testing.
- Session idle/absolute expiry was not waited out.
- The bank statement import accepted only the configured CSV format; malicious file parsing was not fuzzed.
- Audit logs were preserved and not rewritten, but a full tamper-evidence review was not repeated here; existing hash-chain tests remain part of the backend suite.
- The QA environment uses the same permission seed as staging; production secret handling and deployment configuration were out of scope.
