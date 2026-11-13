# Invalid Input and Validation Report

**Evidence:** [api-probe.json](evidence/adversarial/api-probe.json), [adversarial-forms.spec.ts](../../frontend/e2e/adversarial-forms.spec.ts), [form screenshots](evidence/adversarial/)  
**API checks:** 45/45 passed  
**Browser form-attack tests:** 5/5 passed  
**Unintended records created by failed validation:** 0

---

## 1. Scope

Validation was tested at two independent layers:

1. **Real browser forms** — typing hostile or invalid values into the Angular UI and confirming that either the client blocks submission or the backend rejects it with a visible message.
2. **Direct API probes** — bypassing the frontend entirely, using the System Administrator and role-specific accounts against the QA API.

A frontend-only pass is not treated as evidence of backend safety. The direct probe results below are the authoritative backend evidence; the browser tests prove the user receives a clear message.

## 2. Browser attacks

| Test                   | Input                                                                                                        | Result                                                                                                                                                             |
| ---------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Empty supplier form    | No code, no legal name                                                                                       | "Check the highlighted fields.", "Code is required.", "Legal name is required."; **zero POSTs**                                                                    |
| Stored XSS             | Legal name `<script>window.__qaXss=1</script> QA Supplier`; notes `"><img src=x onerror="window.__qaXss=2">` | Record created through the real form; row and detail render the text literally; `window.__qaXss` remained undefined; no browser dialog; no script element executed |
| Negative credit limit  | Customer credit limit `-1`                                                                                   | "Credit limit is too low."; **zero POSTs**                                                                                                                         |
| SQL-like search        | `' OR 1=1 --` in Search Suppliers                                                                            | `200` with zero rows and "No records match this search."; no error banner; no query broadening                                                                     |
| Impossible dates       | Project start `2027-05-10`, end `2027-05-01`                                                                 | Backend `400`; field error "The end date cannot precede the start date."                                                                                           |
| Empty purchase request | No destination, no lines                                                                                     | "Destination is required."; **zero POSTs**                                                                                                                         |
| Executable upload      | `qa-upload.exe` with an MZ header                                                                            | One POST attempted, `400`; visible message "Files of type .exe are not accepted. Allowed: .csv, .docx, .jpeg, .jpg, .pdf, .png, .txt, .webp, .xlsx."               |

Screenshots:

- [Required fields](evidence/adversarial/form-01-required-fields.png)
- [Stored XSS rendered literally](evidence/adversarial/form-02-escaped-xss-detail.png)
- [Negative credit blocked](evidence/adversarial/form-03-negative-credit-blocked.png)
- [SQL-like search](evidence/adversarial/form-04-sql-like-search.png)
- [Impossible dates](evidence/adversarial/form-05-impossible-project-dates.png)
- [Empty purchase request](evidence/adversarial/form-06-empty-purchase-request.png)
- [Executable upload refused](evidence/adversarial/form-07-executable-upload-refused.png)

Traces: captured locally during the adversarial run (session-bearing archives not committed).

## 3. Direct API probe results

### 3.1 Permissions and object access — 11 checks

| Check                                        | Status | Expected |
| -------------------------------------------- | -----: | -------- |
| Operations cannot read company bank accounts |    403 | 403      |
| Operations cannot read supplier invoices     |    403 | 403      |
| Procurement cannot read access users         |    403 | 403      |
| Finance cannot write access roles            |    403 | 403      |
| Management cannot create users               |    403 | 403      |
| Auditor cannot create a supplier             |    403 | 403      |
| Management cannot create a supplier          |    403 | 403      |
| Administrator missing object                 |    404 | 404      |
| Operations missing invoice object            |    403 | 403      |
| Customer PDF requires invoice permission     |    403 | 403      |
| Anonymous cannot read invoices               |    401 | 401      |

### 3.2 Supplier/customer validation — 6 checks

| Check                            | Status | Result                       |
| -------------------------------- | -----: | ---------------------------- |
| Missing required supplier fields |    400 | Refused                      |
| Negative payment terms           |    400 | Refused                      |
| Invalid email                    |    400 | Refused                      |
| Overlong legal name (250 chars)  |    400 | Refused                      |
| Negative customer credit limit   |    400 | Refused after TMD-ADV-02 fix |
| Duplicate supplier code          |    400 | Refused                      |

The negative-credit probe initially posted to `/suppliers/` (a supplier endpoint that ignores customer-only fields), which was a probe-fixture error. It was corrected to `/customers/` and exposed a real backend gap: the API accepted `-1.00` before the fix. The server now rejects it independently of the browser's `min=0`.

### 3.3 SQL-like data handling — 2 checks

| Check                                    | Status | Result                                      |
| ---------------------------------------- | -----: | ------------------------------------------- |
| Party table survives SQL-like legal name |    200 | Table remains usable; literal string stored |
| Supplier search with SQL-like text       |    200 | Treated as text; no broadening, no 500      |

The QA fixtures are `QA-XSS-001` and `QA-SQL-001`. They exist only in the isolated QA clone. The browser test independently created a fresh XSS supplier through the real form and deactivated it afterwards.

### 3.4 Purchase request validation — 5 checks

| Input                  | Status |
| ---------------------- | -----: |
| Empty body             |    400 |
| No lines               |    400 |
| Zero quantity          |    400 |
| Negative quantity      |    400 |
| Unknown catalogue item |    400 |

### 3.5 Customer invoice validation — 7 checks

| Input                     | Status |
| ------------------------- | -----: |
| Empty body                |    400 |
| No lines                  |    400 |
| Zero quantity             |    400 |
| Negative unit price       |    400 |
| Invalid calendar date     |    400 |
| Amount with 21 digits     |    400 |
| Overlong line description |    400 |

Invoice totals are recalculated by the backend; a client-supplied total is not trusted. All failed submissions left the invoice count unchanged.

### 3.6 Invalid state transitions — 12 checks

| Attempted transition                                         | Status |
| ------------------------------------------------------------ | -----: |
| Submit an already-submitted purchase request                 |    409 |
| Approve an already-approved purchase request                 |    409 |
| Receive a purchase order with no lines                       |    400 |
| Submit an already-submitted supplier invoice                 |    409 |
| Approve an already-approved supplier invoice                 |    409 |
| Edit an approved supplier invoice                            |    400 |
| Approve an already-approved customer invoice                 |    409 |
| Approve an already-approved reconciliation                   |    409 |
| Accept an already-accepted work order                        |    409 |
| Dispatch a closed rental agreement (with equipment supplied) |    409 |
| Post an already-posted journal                               |    409 |
| Close an already-closed accounting period                    |    409 |

The rental-dispatch probe initially omitted the required `equipment` field and returned 404; that was a probe-fixture error. Supplying the agreement's equipment returns the intended `409` conflict.

### 3.7 Receipt allocation — 2 checks

| Attempt                                           | Status | Side effect        |
| ------------------------------------------------- | -----: | ------------------ |
| Allocate more than the invoice balance            |    400 | No receipt created |
| Allocate an invoice belonging to another customer |    400 | No receipt created |

## 4. Session and CSRF checks

Seven checks passed against the live QA API:

| Check                        | Result                          |
| ---------------------------- | ------------------------------- |
| CSRF bootstrap               | 200                             |
| Login                        | 200                             |
| Session cookie               | `sessionid` present, `HttpOnly` |
| Authenticated `/me`          | 200                             |
| Mutation without CSRF token  | 403                             |
| Mutation with foreign Origin | 403                             |
| Logout then `/me`            | 204 then 401                    |

The initial session assertion looked for `sessionid` only after logout, when the cookie had correctly been removed. Capturing the login response before logout showed both `csrftoken` and `sessionid`, with `HttpOnly`. This was a probe timing error, not an application defect.

## 5. Side-effect checks

- Supplier count before and after the create-validation probes: **8 → 8**.
- No customer was created by the negative-credit browser test (zero POSTs).
- No project was created by the impossible-date test (backend 400).
- No purchase request was created by the empty-form test (zero POSTs).
- No document was created by the `.exe` upload (one rejected POST).
- No customer receipt was created by over-allocation or wrong-customer allocation.
- No journal was posted, stock moved, approval granted or period closed by any rejected transition.

## 6. Defects from this report

| ID         | Defect                                 | Fix                                                                              |
| ---------- | -------------------------------------- | -------------------------------------------------------------------------------- |
| TMD-ADV-02 | Negative credit limit accepted by API  | Server-side `validate_credit_limit` rejects `< 0`; backend regression test added |
| TMD-ADV-04 | File-upload error hidden from the user | Explicit file-field alert; browser regression test asserts the exact message     |

## 7. Limitations

- File testing used a harmless placeholder `.exe`; no oversized file, corrupt PDF or misleading double-extension was uploaded in this pass. The backend has explicit extension and size checks, but only the extension rejection was exercised end-to-end.
- Telephone/website/Unicode/whitespace-only text was not exhaustively fuzzed on every form; API serializers cover required fields, email, lengths and numeric bounds.
- Financial posting policy remains disabled, so no real invoice was posted to the ledger.
