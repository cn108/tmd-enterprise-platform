# Role-based access acceptance report

**Evidence:** `docs/reports/evidence/role-access-matrix.json`, `role-access-matrix.md`
**Method:** 10 staging identities, 13 access checks each, direct DRF API calls and matching Angular browser checks. 130 API checks passed.

## 1. Matrix exercised

| Role | Read procurement / inventory / services / leasing | Formal financial reports | Bank accounts | Create purchase request | Receive goods | Issue stock | Import statement | Accept work order | Dispatch rental |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| System Administrator (superuser) | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Management | Yes | Yes | Yes | Yes | No | No | No | Yes | No |
| Accountant | Yes | Yes | Yes | Yes | No | No | No | No | No |
| Finance Controller | Yes | Yes | Yes | Yes | No | No | No | No | No |
| Finance Officer | Yes | Yes | Yes | Yes | No | No | Yes | No | No |
| Procurement Officer | Yes | No | No | Yes | Yes | No | No | No | No |
| Project Manager | Yes | No | No | Yes | Yes | No | No | Yes | Yes |
| Storekeeper | Yes | No | No | Yes | Yes | Yes | No | No | No |
| Operations / HSE | Yes | No | No | Yes | No | No | No | No | Yes |
| Auditor | Yes | Yes | Yes | No | No | No | No | No | No |

“No” means the API returned 403. It is least-privilege denial, not a functional failure. The System Administrator is a break-glass superuser and is not a business role.

## 2. Defects found and corrected

| ID | Severity | Defect | Correction | Retest |
| --- | --- | --- | --- | --- |
| RBAC-01 | **High** | The role-matrix `_crud()` helper passed a tuple to `codename__startswith`; Django treated it as one string, so no `view_*`, `add_*` or `change_*` permissions were actually granted for any CRUD bundle. | Build an explicit `Q` OR over the action prefixes. | New regression test plus 130-check matrix |
| RBAC-02 | **High** | No role held `banking.import_bankstatement`, `match_banktransaction`, `submit_reconciliation` or `approve_reconciliation`; the banking workflow was impossible for business users. | Finance Officer: import, match, submit. Accountant/Controller/Management: approve. Controller: approve transfers. | Matrix + workflow |
| RBAC-03 | **High** | Procurement and inventory read endpoints relied only on `IsAuthenticated` (SEC-04). | Added module view-permission mixins to procurement and inventory list/detail/report views. | Matrix, browser read tests |
| RBAC-04 | **High** | Procurement submit/issue/close/receive actions had no explicit permission beyond authentication. | Added `add_purchaserequest`, `change_purchaseorder`, `add_requestforquotation`, `add_supplierquote`, `add_goodsreceiptnote` and related guards. | Procurement tests and matrix |
| RBAC-05 | **High** | Operations and Project Manager could read services and leasing but could not perform their operational actions. | Granted work-order add/change/assign/complete/accept and equipment dispatch/return/inspection bundles. | Matrix + browser |
| RBAC-06 | **Medium** | Auditor saw an enabled “New purchase request” button even though the API would return 403. | Workspace resource now separates create and edit permissions; procurement request uses `add_purchaserequest` / `change_purchaserequest`. | Playwright auditor test |
| RBAC-07 | **Medium** | Every operational role could not raise a purchase request despite the documented policy that every authenticated employee may request. | Added `procurement.add_purchaserequest` to operational roles; Auditor remains read-only. | Matrix |
| RBAC-08 | **Low** | Storekeeper and Procurement Officer could not see engineering work orders or equipment relevant to receipts/issues. | Added read-only services and leasing visibility. | Browser/module checks |

## 3. Unresolved policy decisions

1. The permission matrix remains **provisional (D-03)** and requires management approval.
2. Management has create-request permission but not change-request permission; the UI now reflects this. Management can create a request but cannot edit another user's draft. Confirm this is intended.
3. Project Manager can receive goods. This supports direct project-site deliveries but should be confirmed against warehouse segregation policy.
4. Auditor has broad read access, including bank accounts and financial statements, but no write access. Confirm audit independence requirements.
5. No role can delete master or transaction records; deletion is denied by design.

## 4. Browser acceptance

The Playwright suite verified that:
- a Management user signs in and reaches every business module;
- seeded procurement, inventory, banking, services and leasing records render;
- Operations sees operational reports but no formal financial-statement tab;
- Auditor opens procurement in read-only form and the create button is disabled.

**Result: PASS for controlled UAT.** Access is enforceable and no tested role could exceed its bundle through the API or the portal.
