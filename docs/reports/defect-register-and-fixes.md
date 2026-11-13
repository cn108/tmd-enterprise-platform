# Defect Register and Fixes

**Testing window:** 12–13 November 2026  
**Application defects found and fixed:** 6  
**Critical:** 0  
**High:** 3  
**Medium:** 3  
**Low remaining:** 1 accepted

---

## Summary

| ID         | Severity | Module                  | Defect                                                                                                     | Status |
| ---------- | -------- | ----------------------- | ---------------------------------------------------------------------------------------------------------- | ------ |
| TMD-ADV-01 | High     | Parties / Master data   | Party option endpoint returned 403 for every user because the permission class could not resolve the model | Fixed  |
| TMD-ADV-02 | Medium   | Parties / Customers     | Negative credit limits accepted by the API                                                                 | Fixed  |
| TMD-ADV-03 | High     | Master data forms       | Supplier/customer currency defaulted to null, blocking creation unless NGN was manually selected           | Fixed  |
| TMD-ADV-04 | Medium   | Documents               | Rejected file-upload error was hidden; only a generic message appeared                                     | Fixed  |
| TMD-ADV-05 | Medium   | Procurement / RFQ       | View on RFQ invitations returned 404                                                                       | Fixed  |
| TMD-ADV-06 | High     | Workspace / Report tabs | View on computed report tabs called nonexistent detail endpoints and returned 404                          | Fixed  |

---

## TMD-ADV-01 — Party lookup denied to every role

**Severity:** High  
**Module:** Parties / Master data  
**Roles affected:** All, including System Administrator  
**Discovered by:** API probe `parties_table_survives_sql_like_input`, then confirmed with a superuser permission check

### Reproduction

1. Sign in as System Administrator.
2. Request `GET /api/v1/parties/`.
3. Observe `403 Forbidden`.

### Expected

A user holding `parties.view_party` receives the party options list (200).

### Actual

Even the superuser, with 623 permissions and `parties.view_party = True`, received 403. Any form using the generic party selector (contacts, addresses, tax registrations) could not load its choices.

### Root cause

`PartyViewSet` defined `get_queryset()` but no `queryset` class attribute. `ModelPermission.has_permission()` reads `view.queryset.model`; with no class queryset it returned `False` before checking the user's permission.

### Fix

- Added `queryset = Party.objects.all()` to `PartyViewSet`.
- Changed `get_queryset()` to start from `super().get_queryset()`.

### Regression and re-test

- Existing master-data permission test now asserts `/api/v1/parties/` is 403 without `view_party` and 200 with it.
- 24 party tests pass.
- Probe now passes.

---

## TMD-ADV-02 — Negative customer credit limit accepted

**Severity:** Medium  
**Module:** Parties / Customers  
**Role affected:** Any role with customer write permission  
**Discovered by:** Browser test and corrected API probe

### Reproduction

1. Send `POST /api/v1/customers/` with `credit_limit: "-1.00"`.
2. Observe `201 Created`.

### Expected

`400` with a field error; a credit limit cannot be negative.

### Actual

The API accepted the negative limit. Only the browser's `min=0` validator stopped ordinary users.

### Root cause

The model stored a decimal without a non-negative validator, and `CustomerSerializer` had no `validate_credit_limit`.

### Fix

- Added `validate_credit_limit` rejecting values below zero.
- The response is a standard 400 envelope with a `credit_limit` field message.

### Regression and re-test

- New backend test `test_customer_credit_limit_cannot_be_negative`.
- Browser test confirms the client also blocks it and sends no POST.
- Corrected probe posts to `/customers/`, not `/suppliers/`, and passes.

---

## TMD-ADV-03 — Currency null blocks supplier/customer creation

**Severity:** High  
**Module:** Master data forms  
**Role affected:** Any role creating a supplier or customer  
**Discovered by:** Browser test `required fields, stored XSS and confirmation cancellation`

### Reproduction

1. Open Master data → Suppliers → New supplier.
2. Fill code and legal name; do not change the empty Currency select.
3. Submit.
4. The backend returns "This field may not be null." and no supplier is created.

### Expected

The form uses the configured reporting currency (NGN) by default, matching the model default.

### Actual

Currency began as `null` in every configured currency select. The UI sent an explicit null and the API rejected it. Users had to discover that they must manually choose the only available currency.

### Root cause

`CURRENCY_OPTIONS` supplied the options but the field configuration supplied no `defaultValue`, and `initialValue()` returns null for an untouched select.

### Fix

- Added `defaultValue: 'NGN'` to all nine configured currency fields.
- No new currency was invented; NGN is the only configured option.

### Regression and re-test

- New frontend unit test asserts the supplier form's currency value is NGN.
- Browser supplier creation now succeeds without touching Currency.
- Supplier form test passes.

---

## TMD-ADV-04 — File-upload rejection message invisible

**Severity:** Medium  
**Module:** Documents  
**Role affected:** Any user uploading a disallowed file  
**Discovered by:** Browser test with a real `.exe` file

### Reproduction

1. Open Master data → Documents → New document.
2. Choose `qa-upload.exe`.
3. Submit.
4. Observe only "One or more fields are invalid." with no message beside File.

### Expected

The backend's specific message — "Files of type .exe are not accepted…" — appears beside the File control.

### Actual

The message was present in component state but not rendered. The file input was not bound to the Material form field, and `mat-error` is hidden when the form field has no bound control.

### Root cause

`record-form.component.html` used `<mat-error>` inside the file branch for a control that was not attached via `formControlName`.

### Fix

- Render file errors in an explicit `role="alert"` block beside the upload control.
- Added styling for the error block.

### Regression and re-test

- Browser test asserts the exact extension-rejection text and exactly one failed POST.
- Screenshot: [executable upload refused](evidence/adversarial/form-07-executable-upload-refused.png).
- Trace: captured locally during the adversarial run (session-bearing archive not committed).

---

## TMD-ADV-05 — RFQ invitation View returns 404

**Severity:** Medium  
**Module:** Procurement → RFQ invitations  
**Role affected:** Any role with RFQ view permission  
**Discovered by:** 104-tab interaction sweep

### Reproduction

1. Open Procurement → RFQ invitations.
2. Click View on an invitation.
3. Observe an error banner; no detail dialog.

### Expected

A read-only detail opens for the invitation.

### Actual

`GET /api/v1/rfq-suppliers/1/` returned 404 because the viewset implemented only create and list.

### Root cause

`RfqSupplierViewSet` lacked `RetrieveModelMixin`, while the generic workspace always rendered a View button for rows with an id.

### Fix

- Added `RetrieveModelMixin`; the existing `procurement.view_rfqsupplier` permission still applies.

### Regression and re-test

- New backend test `test_rfq_invitation_detail_is_readable` asserts 200 and the supplier name.
- The full tab sweep passes.

---

## TMD-ADV-06 — Computed report View calls a nonexistent endpoint

**Severity:** High  
**Module:** Banking, Projects, Leasing, Inventory report tabs  
**Role affected:** Any role that can view the report  
**Discovered by:** 104-tab interaction sweep; a read-only detail probe confirmed six 404 endpoints

### Reproduction

1. Open Banking → Banking dashboard (or Reconciliation report, Project dashboard, Profitability, Equipment utilisation or Availability).
2. Click View on a row.
3. Observe a 404 error banner and no dialog.

### Expected

The configured row detail opens.

### Actual

The generic workspace called `/api/v1/{report-endpoint}/{row-id}/`. Those endpoints are computed list APIs with no retrieve route, so every View returned 404.

The read-only endpoint audit confirmed 404 detail responses for:

- `banking-summary`
- `banking-reconciliation-report`
- `project-dashboard`
- `project-profitability`
- `equipment-utilisation`
- `equipment-availability`

Related computed states (`banking-match-suggestions`, `banking-unmatched-transactions`, `stock-balances`, `reorder-alerts`, `equipment-warnings`) either returned no row id or were empty; they were hardened at the same time.

### Root cause

No distinction existed between a model resource with a retrieve route and a computed projection whose detail must come from the loaded row.

### Fix

- Added `detailFromRow?: boolean` to `ResourceConfig`.
- `WorkspaceComponent.view()` opens the local detail when the flag is set, without an API call.
- Set the flag on all affected computed resources.

### Regression and re-test

- New frontend unit test asserts View opens a dialog and makes no `/banking-summary/7/` request.
- Full 104-tab sweep passes with 69 detail dialogs and zero page errors.

---

## Residual issues

### RES-01 — Expected 403 console noise on restricted modules

**Severity:** Low — accepted  
**Where:** Procurement, Project, Store, Operations restricted pages

The browser logs five "Failed to load resource: 403" messages because the workspace asks for a restricted list before rendering Access Restricted. The backend response is correct, no records are shown and no action succeeds. This is console noise, not a bypass. It is retained because a route-level pre-check would add complexity and risk across role-specific tab mixtures.

### RES-02 — Financial activation remains blocked

Not a defect. Production invoice issuance and posting require approved accounting policy, explicit activation and operating controls. The QA environment correctly keeps `can_issue=False` and test mode on. This must remain a management/accounting decision, not an engineering workaround.

### RES-03 — Coverage limits

- 4,718 controls were discovered, but 466 deliberate interactions were performed. The discovered figure repeats navigation and row controls across roles; no 100% click claim is made.
- Session idle/absolute expiry was not waited out; logout invalidation was proven.
- Only `.exe` file rejection was exercised end-to-end; oversized/corrupt/mismatched files remain a coverage gap.
- All 37 disabled controls were counted, but not every tooltip was individually read.
- Destructive lifecycle actions were verified through API/integration tests rather than mass-clicked on seeded rows.

## Test-harness corrections (not application defects)

| Correction                                    | Reason                                                                                               |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Negative-credit probe posted to `/suppliers/` | Supplier endpoint ignores customer-only fields; corrected to `/customers/`, which exposed TMD-ADV-02 |
| Rental-dispatch probe omitted `equipment`     | Returned 404; supplying equipment returned the intended 409                                          |
| Session cookie checked after logout           | The session cookie is correctly removed by logout; capture moved before logout                       |
| Stale Playwright heading/selector assertions  | Old "Welcome" text and removed dashboard widgets were updated to current UI                          |
| Probe output path resolved outside `docs/`    | Corrected CLI invocation; evidence JSON now writes to the repository path                            |
| First tracing hook attempted to start twice   | Removed duplicate tracing setup; Playwright's built-in trace setting is used                         |

## Verification after fixes

| Check               | Result     |
| ------------------- | ---------- |
| Backend             | 343 passed |
| Frontend            | 70 passed  |
| Playwright          | 18 passed  |
| API probe           | 45/45      |
| Session checks      | 7/7        |
| Ruff                | Passed     |
| Migrations          | No changes |
| Frontend lint/build | Passed     |

**Known critical/high/medium defects remaining from this exercise: 0.** Pre-existing production-hardening items tracked in the earlier full-system audit (MFA enforcement, general API throttling) are outside this code change and remain separately tracked.
