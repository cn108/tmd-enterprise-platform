# Technical review — 12 November 2026

**Scope:** invoice posting, supplier cost classification, customer revenue recognition,
WHT, payment and note posting, posting idempotency, company email, permissions, temporary
sharing, and the dashboard/access phase.

**Environment:** isolated `tmd_staging` database with synthetic UAT records.
**Control state:** `InvoiceSettings.test_mode=True`, `activated_at=None`, `can_issue=False`.
**Production activation:** not performed and not authorised.

This review complements, and does not replace, the handover dated 12 November 2026.

---

## 1. Invoice posting logic

**Finding: implemented and tested; one integrity gap was closed during this review.**

`backend/apps/invoicing/posting.py` now:

- locks the invoice row for the whole posting transaction;
- refuses test invoices and unapproved invoices;
- refuses a duplicate post unless the same idempotency key is replayed;
- refuses closed or missing accounting periods;
- resolves every account role through an approved, effective mapping;
- builds balanced supplier and customer journals;
- links the journal back to the invoice and writes an audit event.

Supplier invoice:

- product line → inventory;
- project invoice → project cost;
- other/service line → cost of sales;
- recoverable VAT → input tax;
- non-recoverable VAT → added to the cost line;
- total → accounts payable control.

Customer invoice:

- total → accounts receivable control;
- line subtotal → revenue;
- VAT → output tax.

**Gap closed:** an invoice with approved credit/debit notes can no longer be posted at its
gross value. The service now refuses the post because note posting is not implemented and
the ledger would otherwise disagree with the reduced document balance.

**Residual issue:** the journal posts on the invoice date. This is an accounting policy
assumption, not a verified revenue-recognition rule.

---

## 2. Supplier invoice cost classification

**Finding: partially implemented; classification is a policy assumption.**

Current rule:

| Condition | Debit role |
|---|---|
| Invoice linked to a project | `PROJECT_COST` |
| Product item | `INVENTORY` |
| Anything else, including services | `COST_OF_SALES` |

This is deterministic and does not invent accounts, but it cannot distinguish:

- a product bought for immediate consumption from stock;
- a project service cost from project material;
- a capital item from an expense;
- a cost that should be split across departments or cost centres.

**Recommendation:** obtain an approved line-classification policy before activation. Add a
line-level cost role or an approved item-category mapping only after that policy exists.

---

## 3. Customer revenue recognition

**Finding: partially implemented; the ledger entry is an invoice-date entry, not a
revenue-recognition conclusion.**

The customer journal debits receivables and credits revenue plus output VAT. It does not
consider:

- delivery or service acceptance;
- performance obligations;
- deferred revenue;
- project milestones;
- credit notes raised after the invoice;
- WHT withheld by the customer.

The existing project margin is explicitly labelled an estimate. No revenue-recognition
policy has been supplied.

**Recommendation:** management/accounting must decide whether revenue is recognised on
invoice, delivery, acceptance or milestone completion. Until then, the current posting is a
document-entry policy that must be signed off, not treated as audited revenue.

---

## 4. WHT treatment and tax functionality

**Finding: calculation is implemented; ledger posting is blocked.**

- Supplier and customer lines can carry a WHT code.
- WHT is calculated on line subtotal, excluding VAT.
- Supplier `payment_due` deducts WHT.
- Customer `net_receivable` deducts WHT.
- Invoice posting explicitly refuses any invoice with `wht_total != 0`.
- Supplier payment posting also refuses an allocated invoice with WHT.
- There are no WHT payable or WHT receivable account roles in the current 19-role chart.
- There is no WHT remittance, certificate or tax-return workflow.

The current behaviour is deliberately conservative: no journal is posted with an
unapproved WHT treatment.

**Blocked by:** tax adviser and Finance Controller approval of the WHT base, withholding
point, payable/receivable accounts, remittance owner and certificate process.

---

## 5. Payment and credit/debit note ledger posting

**Finding: supplier payment posting is implemented; notes are not.**

### Supplier payments — implemented

`post_supplier_payment` now:

- requires Stage 7B activation;
- refuses test payments;
- requires a recorded payment;
- requires an open accounting period;
- requires every allocated invoice to be approved and already posted;
- refuses WHT invoices and invoices with approved notes;
- debits AP control for allocated amounts;
- debits supplier advances for the unallocated remainder;
- credits the company bank account's GL account, or the `BANK` / `CASH` role;
- links the journal and writes `supplier_payment.posted`;
- supports replay with `Idempotency-Key`.

The UI exposes **Post to ledger** only for a recorded payment and only to roles with
`invoicing.post_supplierpayment`.

### Credit and debit notes — not implemented

The note model has no journal link. There is no note posting service, endpoint or UI action.
Because a note line carries only description, quantity, price and VAT — not the original
cost role or item classification — a safe supplier-note journal cannot be derived yet.
Customer notes are simpler in principle but still require an approved revenue/tax treatment.

**Guard added:** an invoice with an approved note is refused for invoice posting and for
payment posting until note posting exists. This prevents a partial ledger.

### Customer receipts — not implemented

There is no customer receipt model or allocation workflow. The dashboard therefore shows
customer receipts from bank transactions only when such records exist; it does not invent
them.

---

## 6. Invoice posting idempotency

**Finding: implemented for invoices and supplier payments.**

- `IdempotencyRecord` is unique on `(scope, key)`.
- Invoice scopes are `invoice.post:supplier:{id}` and `invoice.post:customer:{id}`.
- Payment scope is `payment.post:{id}`.
- The client may send `Idempotency-Key`; the API falls back to a deterministic document key.
- A replay returns the original journal and `Idempotency-Replayed: true`.
- A different key cannot post an already-posted document; it receives the normal conflict.
- The invoice/payment row is locked before the receipt is checked.

Automated tests cover a replayed invoice post and a replayed payment post without creating a
second journal.

---

## 7. Company email configuration and test-recipient restrictions

**Finding: delivery is implemented and configured; there is no recipient allowlist by
design.**

- Sender: personal demonstration mailbox (redacted); production now requires a company-controlled identity.
- SMTP credentials live in git-ignored `backend/.env`; they are not in the repository.
- Approved supplier and customer invoice PDFs can be emailed to any valid address.
- The earlier test-mailbox restriction was deliberately removed in the previous session.
- Only roles with the invoice email permission can send.
- Only approved invoices can be sent.
- Test PDFs retain the `TEST DOCUMENT — NOT A TAX INVOICE` banner.
- Successful sends are audited.

**Residual risk:** a permitted user can send a test invoice PDF to any external address.
There is no domain allowlist, bounce handling, delivery webhook, retry queue or per-recipient
rate limit.

**Required before production:** company-domain sender, SPF/DKIM/DMARC, reply-to owner,
recipient policy, bounce handling and email retention decision.

---

## 8. Access permissions for posting and email

**Finding: restricted by backend permission and reflected in the UI.**

Current role grants:

| Capability | System Administrator | Accountant | Finance Controller | Management | Finance Officer | Other roles |
|---|---|---|---|---|---|---|
| Post supplier invoice | Yes | Yes | Yes | No | No | No |
| Post customer invoice | Yes | Yes | Yes | No | No | No |
| Post supplier payment | Yes | Yes | Yes | No | No | No |
| Email supplier/customer invoice | Yes | Yes | Yes | Yes | Yes | No |

The role matrix was re-applied to staging after adding `invoicing.post_supplierpayment`.
The Finance Controller browser view correctly shows **Limited actions**, a disabled
**New supplier payment** control, and an enabled **Post to ledger** action.

The Auditor remains read-only. Backend permission classes remain authoritative; disabled
Angular controls are presentation only.

**Residual:** MFA is not enforced, so a stolen password can still satisfy an approval step.

---

## 9. Staging tunnel and sharing security

**Finding: suitable only for temporary synthetic demonstrations.**

Current public URL:

```text
https://happen-fioricet-kid-issn.trycloudflare.com
```

- Cloudflare Quick Tunnel to the Angular dev server on `127.0.0.1:49630`.
- Vite proxies `/api` to Django on `127.0.0.1:8000`.
- The tunnel rewrites the Host header to `localhost`.
- Authentication is required; the URL does not bypass the login screen.
- All visible records are synthetic staging data.
- The Gmail App Password and `.env` are not exposed by the tunnel.

Residual risks:

- Quick Tunnel is ephemeral and has no uptime guarantee.
- There is no app-layer IP allowlist or second factor in front of the login page.
- Development cookies are not marked `Secure`; the tunnel is HTTPS but the dev settings do
  not add TLS-only cookie flags.
- Mutating requests through the tunnel are likely to fail Django CSRF origin checks because
  the ephemeral tunnel origin is not in `CSRF_TRUSTED_ORIGINS`. This is safer for a
  read-only family demonstration but must not be treated as working remote administration.
- The tunnel should be stopped when the demonstration ends.

---

## 10. UI/UX phase, dashboard and access indicators

**Finding: the earlier UI/UX phase is present and the dashboard was extended in this
review.**

Existing:

- role-focused dashboard with financial, invoice, action, operations and activity sections;
- omitted sections when the role lacks the source permission;
- honest empty states instead of invented zeros;
- test-environment and test-document labels;
- View only, Limited actions and Access restricted states in the workspace;
- the same access card in Reports and Administration;
- preserved navy/gold palette, header and page structure.

Added in this review:

- a complete **Business modules** grid covering all eleven modules, including Invoices,
  Reports and Administration;
- a role-aware **Restricted** badge on modules the account cannot open;
- restricted modules remain visible with **View access status** rather than disappearing;
- backend `module_access` data based on real view permissions.

Browser evidence:

| Evidence | Path |
|---|---|
| Finance Controller dashboard, module-access badge | `docs/reports/evidence/uiux/dashboard-module-access-controller-bottom-2026-11-12.png` |
| Restricted Administration page | `docs/reports/evidence/uiux/access-restricted-controller-2026-11-12.png` |
| Test-mode payment posting refused | `docs/reports/evidence/uiux/payment-post-blocked-test-mode-2026-11-12.png` |
| Full dashboard header and financial overview | `docs/reports/evidence/uiux/dashboard-controller-module-access-2026-11-12.png` |

The dashboard stylesheet remains 7.99 kB against the 8 kB error budget. It is below the
error threshold but still above the 6 kB warning budget; no budget was raised or suppressed.

---

## 11. Verification performed

| Check | Result |
|---|---|
| Backend full suite | **316 passed** |
| Focused invoicing/reporting suite | **66 passed** |
| Frontend unit tests | **53 passed** |
| Frontend lint | Passed |
| Frontend production build | Passed |
| Django system check | Passed |
| Ruff | Passed |
| Migration drift | No changes detected |
| Browser login and dashboard | Passed |
| Browser restricted module indicator | Passed |
| Browser test-mode payment posting | Refused with controlled 409 |
| Successful payment posting in browser | Not performed; test mode forbids it |
| Production activation | Not performed |

---

## 12. Conclusion

The invoice and payment posting paths are materially stronger than at handover, and the
dashboard now communicates module access before a user opens a page. The remaining gaps are
not cosmetic: credit/debit note posting, customer receipts, WHT accounts, cost-classification
policy and revenue-recognition policy all require accounting decisions before further
automation is safe.

**Production financial activation remains blocked. Test mode, synthetic data and the
activation gate must stay in place.**
