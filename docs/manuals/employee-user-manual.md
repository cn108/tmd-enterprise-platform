# Employee user manual

## 1. Sign in

1. Open the TMD platform URL supplied by your administrator.
2. Enter your work email and password.
3. If your administrator requires multi-factor authentication (MFA), open the authenticator app and enter the current six-digit code. On first use, scan the setup key or add the account manually, then keep the one-time recovery codes in a safe place.
4. If your account is locked after repeated failures, wait for the lockout period or contact an administrator. Do not share passwords, authenticator codes or recovery codes.

Sessions expire after one hour of inactivity and after twelve hours in total. Use **Sign out** on a shared computer.

If you lose your authenticator, contact an administrator. Recovery requires identity verification and is recorded in the audit trail. Do not ask another user to sign in for you.

## 2. Navigation

The top navigation exposes only modules your role can use:

**Dashboard · Master data · Procurement · Inventory · Accounting · Invoices · Banking · Projects · Services · Leasing · Reports · Administration**

A missing link means your role does not have that permission. Do not attempt to reach it by typing a URL; the server enforces access.

## 3. Standard list screens

Each module workspace uses the same pattern:

- **Search** sends the term to the server and searches the configured fields.
- **Filters** narrow by status or related record.
- **Columns** show the fields relevant to that tab.
- **New** opens the create form. Required fields are marked.
- **Open** shows the full record and available actions.
- **Export** is available only where the module provides it and your role permits it.

Lists are paginated. Changing page or search discards unsaved form input, so save before navigating away.

## 4. Create and edit rules

- Codes must be unique and are usually upper-cased by the server.
- Records are **deactivated**, not deleted. Clear **Active** to retire master data.
- Transaction documents move through controlled statuses; the server rejects invalid transitions.
- Approved documents and posted journals cannot be edited. Use cancellation, reversal or a correction document.
- The server validates permissions and business rules even when a button is hidden.

## 5. Approvals

Where an approval is required:

1. Submit the document.
2. An authorised approver reviews it.
3. A user may not approve their own restricted transaction.
4. The approval or rejection and its reason are recorded in the audit trail.

If no approver is configured, the document remains pending. Contact management; do not bypass the workflow through another account.

## 6. Documents

Uploads are private. Only authenticated users with access can download them, and each download is audited. Allowed file types and the size limit are set by the administrator. Do not upload executable files or malware.

## 7. Reports

Open **Reports** for the management workspace. Formal financial statements come from posted journal lines. Operational figures are labelled as document, commitment or estimate values. Read the completeness warnings before using a figure.

See the [Reporting manual](reporting-manual.md).

## 8. When something is wrong

- **Session expired:** sign in again. Unsaved work is lost.
- **403 / permission denied:** your role lacks the action; ask an administrator for a role review.
- **409 / conflict:** the record changed or the status transition is invalid. Reload and check the current status.
- **Validation error:** read the field message; do not retype the same invalid value.
- **Unexpected server error:** note the time, screen and any request reference, then contact support. Do not retry a financial submission repeatedly.

## 9. Training boundary

Training and UAT records must be clearly identified as test records. Do not use real bank instructions, real customer invoices or real supplier payments during training.
