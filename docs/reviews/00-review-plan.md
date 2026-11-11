# Review Programme: Order, Participants, Gates

**Version:** 1.0 — 11 November 2026
**Approved sequence (management direction):**
1. Management review — authority, spending limits, departments, responsibilities
2. Finance review — chart of accounts, tax treatment, inventory valuation, accounting policies
3. Operational review — how procurement, warehouse, project delivery and invoicing actually work
4. Phase 1 — technical foundation only, with no unapproved business logic

**Purpose of this document:** make that sequence executable. Each review has a pack with blank worksheets, a defined output and a gate. Nothing in the packs proposes company policy; the reviewers supply the values.

---

## 1. Why this order is correct

| Step | What it locks down | What breaks if skipped |
| --- | --- | --- |
| 1. Management | Who may approve what, and for how much | The approval engine is built on guesses; every later workflow inherits the error |
| 2. Finance | The accounts and policies every posting depends on | Journals cannot be enabled at all; valuation and revenue figures would be wrong |
| 3. Operations | The real steps, evidence and exceptions in each department | Screens are built for a process nobody performs; staff revert to spreadsheets |
| 4. Phase 1 | Repository, CI, database and auth | — (safe to do last, and safe to start as soon as step 1 clears) |

Within steps 2 and 3 there is one dependency worth noting: **inventory valuation (step 2) constrains how stock issues are costed (step 3)**, so if the accountant cannot attend early, hold the stock-issue walkthrough until valuation is settled rather than guessing.

## 2. Gate model

| Gate | Cleared by | Unblocks |
| --- | --- | --- |
| **G0** — Scope approved | Management signs D-01 and D-13 (out-of-scope list) | Phase 1 |
| **G1** — Authority defined | D-03, D-04, D-04a, D-04b, D-17, D-18 signed | Phase 2 (identity, roles, approvals) |
| **G2** — Accounting defined | D-05 (CoA + periods), D-06 (valuation/GRNI), D-19 (revenue), D-20, D-21, D-23, D-08 (numbering), D-26 signed by accountant | Phase 5, 6, 7, 8 |
| **G3** — Operations confirmed | Each route in `04-workflows.md` signed by its department owner; Q-09 to Q-23 answered | Phases 3, 4, 5 |

Phases 3 and 4 also need G1 and part of G2, so the practical rule is: **G0 first, then G2 and G3 in parallel, with G1 closed inside the management review.**

## 3. Sessions and inputs

| # | Session | Attendees (minimum) | Duration (proposed) | Pack |
| --- | --- | --- | --- | --- |
| 1 | Management review | MD/management, department heads, finance lead | 2 hours | `01-management-review-pack.md` |
| 2 | Finance review | Accountant, tax adviser (or written input), finance lead | 2–3 hours | `02-finance-accounting-review-pack.md` |
| 3a | Procurement walkthrough | Procurement lead + one buyer | 90 min | `03-operational-review-pack.md` |
| 3b | Warehouse walkthrough | Storekeeper supervisor | 60 min | `03-operational-review-pack.md` |
| 3c | Projects / delivery walkthrough | Project manager(s), operations | 90 min | `03-operational-review-pack.md` |
| 3d | Finance operations walkthrough | Accounts officer (invoices, payments, bank) | 90 min | `03-operational-review-pack.md` |

Durations are suggestions for scheduling, not a commitment. If a session cannot be held, the questions can be answered in writing — the register records who answered and when, either way.

## 4. Rules for the reviews

1. **No decisions from memory.** If nobody can state a rule with confidence, it is recorded UNRESOLVED with an owner and date, not guessed.
2. **One owner per decision.** "Management" as a collective is acceptable for D-01 only; the rest need a named person.
3. **Evidence over description.** A blank form beats a verbal description; a redacted invoice beats both.
4. **Policy is written down at the meeting.** A worksheet with values and signatures is the record; discussion that is not written does not exist.
5. **No software demonstration during policy review.** Showing screens while deciding accounting policy invites "make it like the demo" decisions.
6. **Unresolved items do not block the whole build.** They block only the phase named in the register, and that feature stays disabled.

## 5. Outputs of the programme

| Output | Where it lands |
| --- | --- |
| Signed decisions | `13-decision-register.md` (label flips to CONFIRMED, name and date added) |
| Answered questions | `11-questions.md` §7 answer log |
| Completed worksheets | Retained in `docs/reviews/` as signed copies (scans or filled markdown) |
| Refined workflows | `04-workflows.md` updated to match what was said, with the department sign-off line filled |
| Route sign-offs | `03-operational-review-pack.md` §7 |
| Phase 1 authorisation | `05-phase1-readiness.md` entry criteria |

## 6. What happens after each session

1. Within one working day, the pack's worksheets are transcribed into the decision register with labels and owners.
2. Any answer that conflicts with an existing document is flagged, and the document is corrected — not quietly overruled.
3. `04-review-tracker.md` is updated (gate status, next session, open blockers).
4. Only then does the next phase's work begin.

## 7. Scheduling note

No calendar dates are proposed here: the brief warns against timetable pressure overriding financial correctness (R-24). Set dates with the participants, record them in the tracker, and keep the sequence. If management wants to compress, the safe compression is overlapping sessions 2 and 3 — never skipping them.

## 8. Where to start

Open `01-management-review-pack.md`. Bring the pre-read listed there (three short documents), and expect to leave with D-01, D-02, D-03, D-04 and the hosting answer settled — which is exactly enough to authorise Phase 1.
