# Review Tracker

**Version:** 1.0 — 11 November 2026
**Use:** update after every session. This is the single view of where the programme stands. Nothing here is a commitment to a date until the participants agree it.

---

## 1. Gate status

| Gate | Requires | Status | Notes |
| --- | --- | --- | --- |
| G0 — Scope approved | D-01, D-13 signed | **Partially signed** — D-01 confirmed 11 Nov 2026; D-13 still open | Phase 1 authorised and complete; D-13 signature still needed |
| G1 — Authority defined | D-03, D-04, D-04a, D-04b, D-17, D-18 | **Not started** | Part of management review |
| G2 — Accounting defined | P-01, P-04, P-05/P-06 minimum; D-05, D-19, D-20, D-21, D-23, D-08, D-26 | **Not started** | Blocks Phases 5–8 |
| G3 — Operations confirmed | Route A/B/C + order-to-cash + cash sign-offs; Q-09…Q-23 answered | **Not started** | Blocks Phases 3–5 |

Status values: Not started · Scheduled (date) · Held — awaiting sign-off · Signed · Partially signed (list gaps).

## 2. Sessions

| # | Session | Required attendees | Date agreed | Held | Outputs captured | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Management review | MD, dept heads, finance lead |  | ☐ |  |  |
| 2 | Finance review | Accountant, tax adviser, finance lead |  | ☐ |  |  |
| 3a | Procurement walkthrough | Procurement lead, buyer |  | ☐ |  |  |
| 3b | Warehouse walkthrough | Storekeeper supervisor |  | ☐ |  |  |
| 3c | Projects walkthrough | Project managers, operations |  | ☐ |  |  |
| 3d | Finance operations walkthrough | Accounts officer |  | ☐ |  |  |

## 3. Decision routing

| Review | Decisions it must close | Phase it unblocks |
| --- | --- | --- |
| Management | D-01, D-02, D-03, D-04, D-04a, D-04b, D-10, D-12, D-13, D-17, D-18 | Phase 1 (D-01, D-10), Phase 2 (D-03, D-04, D-17, D-18), Phase 3 (D-02) |
| Finance | D-05, D-06, D-07, D-08, D-11a/b/c, D-19, D-20, D-21, D-22, D-23, D-24, D-25, D-26 | Phase 5, 6, 7, 8, 13 |
| Procurement | D-14, plus Q-12, Q-13, Q-15, Q-16, Q-17b, Q-20, Q-20b, Q-20c, Q-21 | Phase 4 |
| Warehouse | Q-17, Q-17c, Q-18 (with finance), Q-19, Q-19b, Q-19c, D-15 | Phase 5 |
| Projects / operations | D-16, Q-14b, Q-23b, Q-27, Q-27b, Q-31 | Phases 3, 8, 10 |
| Finance operations | Q-20, Q-33, Q-33b, Q-25 | Phase 8, 9 |

## 4. Decision outcome log

Fill one row per decision as it closes. The label must match `13-decision-register.md`; "CONFIRMED" requires a name and date.

| Decision | Label | Decided value | Owner | Date | Evidence (pack page / scan) |
| --- | --- | --- | --- | --- | --- |
| D-01 | CONFIRMED | Phase 0 scope and phased plan approved; Phase 1 authorised | Management | 11 Nov 2026 | Written instruction to scaffold Phase 1; `13-decision-register.md` D-01 |
| D-09 | CONFIRMED | Django/DRF + Angular + PostgreSQL + Redis + Docker Compose + GitHub Actions | Management / IT | 11 Nov 2026 | Same instruction named the stack; `13-decision-register.md` D-09 |

## 5. Blocking items by phase

| Phase | Blocked until | Currently blocking |
| --- | --- | --- |
| 1 | D-01, D-09 or accepted default, D-10, D-12 | **Cleared for local development** on 11 Nov 2026: Phase 1 delivered. D-10 (hosting) and D-12 (support owner) still block Phase 12. |
| 2 | D-03, D-04, D-04a/b, D-17, D-18 | Management review |
| 3 | D-02, Q-14b | Management + projects |
| 4 | D-04, Q-12, Q-13, Q-15, Q-16, Q-20, Q-20b | Management + procurement |
| 5 | D-06, Q-18, Q-19, Q-17 | Finance + warehouse |
| 6 | D-05 (hard), D-19, D-20, D-21, D-23, D-26 | Finance review |
| 7 | D-07, D-08, D-23 | Finance + tax adviser |
| 8 | D-19, D-25, Q-33 | Finance |
| 9 | Q-33b | Finance operations |
| 10 | D-24, Q-27, Q-27b | Finance + operations |
| 11 | D-26 | Finance review |
| 12 | D-10, D-12, Q-35 (RPO/RTO) | Management + IT |
| 13 | D-11 series, Q-30, Q-32 | Finance + management |

## 6. How the tracker is maintained

1. After each session: update the session row, gate status and any closed decisions.
2. Transcribe answers into `11-questions.md` §7 and decisions into `13-decision-register.md`.
3. Where an answer contradicts a document, correct the document the same day and note it in the session row.
4. Re-check the blocking table: any phase whose blockers are all cleared can be scheduled.
5. Never mark a gate signed without a name and a date against it.
