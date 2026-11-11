# Phase Completion Report Template

Use this template at the end of every phase. It follows Guide §14 (mandatory reporting format). A phase is not complete until this report exists and its evidence is reviewable.

---

## Phase: [number and name]

**Date:** [date]
**Prepared by:** [name/role]
**Status:** ready for review / not ready

### Requirements addressed

[List requirement IDs from `03-srs.md`, e.g. PRC-01, PRC-02, INV-01]

### Implemented

[Features and workflows actually working, described in business terms. Do not claim completion because a page renders or an endpoint returns 200.]

### Files/modules changed

[List]

### Database changes

[Migrations, with rationale. Note any data backfill, index or constraint added and why.]

### Tests run

| Command | Result |
| --- | --- |
| [e.g. `pytest`] | [pass/fail counts, exit status] |

Report failures honestly, including tests that could not run and why.

### Acceptance evidence

- Automated output: [path/summary]
- Reconciliation evidence: [figures and where they reconcile]
- UAT scenario(s): [who performed, what they did, outcome]
- Source-to-report trace example: [document → movement → journal → report line]

### Unresolved decisions

| ID | Decision | Owner | Impact if unanswered |
| --- | --- | --- | --- |
|  |  |  |  |

### Risks and limitations

| Risk | Severity | Mitigation / workaround |
| --- | --- | --- |
|  |  |  |

### Recommendation

[Ready for review / not ready, with the specific reason.]

### Next phase proposal

[What starts next, what it depends on, what must be decided first.]

---

## Rules for this report

- Financial features are never reported as production-ready without accountant approval of the relevant policy.
- "Implemented" means code, tests, documentation and acceptance criteria are all satisfied (Guide §9).
- Any deviation from an approved requirement is recorded, not quietly absorbed.
- No real company data, credentials or personal data appear in this report or its attachments.
