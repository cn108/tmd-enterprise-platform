# Accessibility Acceptance Report

**Date:** 12 November 2026  
**Standard:** WCAG 2.1 A/AA automated checks plus keyboard and responsive inspection  
**Tool:** axe-core 4.10.2 injected into the running staging frontend

## Result

Automated axe scans returned **zero violations** for WCAG 2.0/2.1 A and AA on the tested signed-in surfaces:

| Surface | URL | Result |
|---|---|---|
| Customer receipts list | `/invoicing?tab=customer-receipts` | 0 violations |
| New receipt form and validation state | same, dialog open and submitted empty | 0 violations |
| Credit and debit notes | `/invoicing?tab=notes` | 0 violations |
| Banking | `/banking` | 0 violations |
| Administration roles | `/administration?tab=roles` | 0 violations |
| Reports | `/reports` | 0 violations |

## Keyboard and focus

- Tab from page load reached the **Sign out** button with no mouse interaction.
- Focus outline was visibly present: `rgb(232, 182, 76) solid 2px`.
- Dialog focus is trapped inside the modal; Escape closes it.
- Table sort headers, pagination and action buttons are native buttons and keyboard reachable.

## Forms, labels and validation

- Every receipt field exposes a programmatic label through Material form fields.
- Submitting an empty form displays an alert, field-level errors, and `aria-invalid="true"` on invalid controls.
- Required customer, date, amount and method are announced as required.
- **Defect fixed:** the numeric amount input previously displayed an error but did not expose `aria-invalid`. Explicit `aria-invalid` bindings were added to text, textarea, select and line controls.
- Native selects/date inputs retain accessible names and roles in the accessibility tree.

## Headings and structure

- One H1 per module after the earlier duplicate-brand-heading fix.
- Region headings are sequential; tables have captions and column headers; navigation is labelled `Business modules`.
- Status and alert messages use `role="status"` / `role="alert"`.

## Colour contrast and responsive usability

- Axe colour-contrast rule produced no violations.
- At 360 px the receipt viewport had `scrollWidth=343` against `innerWidth=360`: no horizontal page overflow.
- The receipt dialog stacks fields to one column, keeps validation messages visible and keeps Cancel/Create actions in the sticky footer.
- Wider checks at 1366 px and earlier 1920/1024/768/390 checks remained free of page overflow.

## Evidence

- `docs/reports/evidence/final/receipts-approval-ui-1366.png`
- `docs/reports/evidence/final/receipt-create-form-1366.png`
- `docs/reports/evidence/final/receipt-form-validation-1366.png`
- `docs/reports/evidence/final/receipts-approval-ui-360.png`
- `docs/reports/evidence/final/administration-privileged-role-1366.png`

## Limitations

- Automated axe checks do not prove screen-reader task success. A manual NVDA/VoiceOver pass by TMD is still required for formal sign-off.
- Files, PDFs and third-party embedded content were not scanned.
- Axe was injected from the public CDN for this run; no axe package was added to the project dependencies.