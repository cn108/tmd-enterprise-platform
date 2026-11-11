# Question and Evidence Register

**Version:** 0.1 — 11 November 2026
**Guide references:** §9 Phase 0 step 2–7, §15.3, §15.9
**How to use:** Answer in the "Answer" column or return the evidence named. Every answer is copied into `13-decision-register.md` with its label and owner. Questions marked **BLOCKER** must be answered before the phase named in the last column; the rest can be answered during Phases 1–3.

Priority legend: **B** = go-live blocker · **H** = high-risk decision · **P** = operational preference · **L** = later enhancement.

---

## 1. Management (owner: MD / management team)

| ID | Priority | Question | Why it matters | Evidence wanted | Blocks |
| --- | --- | --- | --- | --- | --- |
| Q-01 | H | How are procurement, stock and project costs recorded today (documents, spreadsheets, WhatsApp, notebooks)? | Determines training, migration and interim controls | Copies of current files (redacted) + 30-min walkthrough | Phase 3 |
| Q-02 | B | Who are the department heads and who owns each process end to end? | Named owners for every exception and approval | Org chart / names list | Phase 2 |
| Q-03 | H | Which decisions must management personally approve, and which are delegated? | Approval matrix structure | Written list | Phase 2 |
| Q-04 | B | How many legal entities, and is a single company the only entity transacting? | Multi-entity scoping in the schema | Company registration details (entity count only) | Phase 1/3 |
| Q-05 | B | How many offices, warehouses and active project sites will use the system? | Warehouse/location model, deployment | List of locations | Phase 3 |
| Q-06 | H | Is there more than one store/warehouse per site, and who is responsible for each? | Stock ownership and permissions | List | Phase 5 |
| Q-07 | B | Should users see only their department/project data, or all data with role limits on actions? | Record-level permission design | Decision | Phase 2 |
| Q-08 | B | Which roles exist, and who currently holds more than one role? | Permission matrix realism and segregation of duties | Role-to-person mapping | Phase 2 |
| Q-09 | **B** | What are the approval limits by amount, department, project and document type? | **Approval engine cannot be configured without this** | Written table | Phase 2/4 |
| Q-10 | B | What are the delegation rules and escalation time limits for overdue approvals? | Delegation and escalation build | Written rules | Phase 2 |
| Q-11 | H | How should an over-budget or no-budget request be handled — block, or route to an authorised approver? | Procurement control behaviour | Decision | Phase 4 |
| Q-12 | H | Above what value are multiple quotations mandatory, and who evaluates them? | RFQ design and thresholds | Written rule | Phase 4 |
| Q-13 | H | May anyone raise a PO without a purchase request? If so, who and up to what value? | Direct-PO pathway and controls | Decision | Phase 4 |
| Q-14 | P | Is a single unit of measure enough per item, or are conversions needed (e.g. bags vs tonnes)? | UoM model | Examples | Phase 3 |
| Q-30 | H | What historical data exists, in what formats, and who owns each source? | Migration feasibility | Inventory list of files | Phase 13 |
| Q-32 | B | What migration cut-off date and opening balance approach will be used? | Cutover plan | Written decision | Phase 13 |
| Q-35 | B | What are the acceptable RPO and RTO (how much data may be lost, how long may the system be down)? | Backup/DR design — must not be invented | Written decision | Phase 12 |
| Q-37 | P | How many users, roughly how many concurrent, and what devices? | Performance sizing and UI design | Estimate | Phase 1 |
| Q-38 | P | Is mobile/browser-only acceptable, and do field staff need phone access? | UI scope | Decision | Phase 8 |
| Q-39 | H | What internet availability exists at offices and project sites? Any generator/power constraints? | Hosting and offline strategy | Description per site | Phase 1 |
| Q-40 | H | What is the target go-live window and budget envelope? | Sequencing — noted only, not used to skip controls | Written answer | Planning |

## 2. Procurement (owner: procurement lead)

| ID | Priority | Question | Why it matters | Evidence wanted | Blocks |
| --- | --- | --- | --- | --- | --- |
| Q-15 | H | Can one PO deliver to both a warehouse and a project site, or must orders be split? | Fulfilment/child-record model | Description of a real example | Phase 4 |
| Q-16 | H | Who physically receives goods at warehouse and at site, and what evidence is captured (photo, signed waybill, stamp)? | Receiving roles and attachment requirements | Blank delivery note / GRN | Phase 4 |
| Q-17 | P | Which items need batch/lot, serial or expiry tracking? | Inventory traceability configuration | Category list | Phase 3/5 |
| Q-17b | H | Is over-delivery ever accepted? What tolerance is allowed? | Receipt validation rules | Written tolerance | Phase 4 |
| Q-17c | P | Are customer-supplied or client-owned materials held at TMD sites? | Stock ownership model | Examples | Phase 5 |
| Q-19 | H | Should the system ever permit negative stock? If so, under what approval? | Stock control rules | Decision | Phase 5 |
| Q-20 | H | Which documents must be attached before an invoice can be approved (PO, GRN, waybill, invoice scan)? | Validation and audit evidence | Sample document set | Phase 4/7 |
| Q-20b | H | Can one supplier invoice cover multiple POs, and can one delivery cover multiple POs? | Invoice↔PO↔receipt cardinality | Examples | Phase 4/7 |
| Q-20c | P | How are transport, clearing and handling costs charged by suppliers? | Landed-cost handling (with accountant) | Sample invoices | Phase 5/7 |
| Q-21 | P | Are supplier advances/deposits common? Under what terms? | Advance handling design | Examples | Phase 8 |

## 3. Warehouse / stores (owner: storekeeper supervisor)

| ID | Priority | Question | Why it matters | Evidence wanted | Blocks |
| --- | --- | --- | --- | --- | --- |
| Q-22 | **B** | What chart of accounts, financial year and period-close routine does TMD use today? | **Posting cannot be built without it** | Accountant-provided CoA | Phase 6 |
| Q-18 | **B** | Which inventory costing method is approved (e.g. FIFO, weighted average, specific identification)? | Valuation and COGS correctness | Accountant decision | Phase 5 |
| Q-18b | **B** | Should goods received not invoiced be held on a GRNI account between receipt and invoice? | Posting flows E-02/E-03 | Accountant decision | Phase 6/7 |
| Q-22b | H | Who may reopen a closed period, and what evidence is required? | Period control design | Written rule | Phase 6 |
| Q-22c | P | Rounding preference on invoice lines and tax (per-line vs per-invoice)? | Rounding correctness | Accountant decision | Phase 6/7 |
| Q-19b | H | How often are physical stock counts taken, and who witnesses? | Count workflow | Current practice description | Phase 5 |
| Q-19c | P | Are there items stored at project sites rather than warehouses, and who controls them? | Location model | Examples | Phase 5 |

## 4. Projects and operations (owner: project managers / operations)

| ID | Priority | Question | Why it matters | Evidence wanted | Blocks |
| --- | --- | --- | --- | --- | --- |
| Q-14b | B | What cost-code / cost-centre structure is used on projects, and is it hierarchical? | Project costing and reporting | Existing code list | Phase 3 |
| Q-23 | H | How is revenue recognised — on milestone acceptance, on completion, on invoicing? | **Financial statements depend on it** | Accountant decision | Phase 6/8 |
| Q-23b | P | Do customers pay against contracts rather than invoices in some cases? | AR model | Examples | Phase 8 |
| Q-27 | H | Is labour tracked per project (timesheets), and is it costed to projects? | Cost model and payroll boundary | Examples | Phase 10 |
| Q-27b | H | Does TMD lease equipment out to others, rent in, or both? | Asset module scope | Examples of contracts | Phase 10 |
| Q-28 | H | How long must documents and records be kept, per category? | Retention configuration | Adviser guidance | Phase 3/12 |
| Q-31 | P | Which documents must be printable/PDF at launch (PO, GRN, invoice, statement, report packs)? | PDF scope | Sample formats | Phase 7 |

## 5. Finance / accounts (owner: accountant / finance lead)

| ID | Priority | Question | Why it matters | Evidence wanted | Blocks |
| --- | --- | --- | --- | --- | --- |
| Q-24 | **B** | What tax registrations apply, and which tax codes/rates must invoices carry? | Invoicing correctness and compliance | Adviser-confirmed list | Phase 7 |
| Q-24b | H | How is VAT treated on TMD's sales and purchases (rates, exemptions, reverse charge)? | Tax configuration | Adviser guidance | Phase 7 |
| Q-24c | P | Does TMD withhold tax on any supplier payments? | WHT handling if in scope | Adviser guidance | Phase 8 |
| Q-25 | H | Will there be foreign-currency purchases or sales? Which currencies? | FX design and enablement | Contract examples | Phase 6 |
| Q-26 | **B** | What is TMD's current NRS e-invoicing onboarding/implementation status, and is an API available to TMD? | Fiscal adapter scope and compliance | Official correspondence/docs | Phase 7 |
| Q-26b | P | Does TMD expect accounting to remain in a separate bookkeeping package, requiring an export? | Determines whether an export integration is needed at all | Decision | Phase 11 |
| Q-29 | H | What data-protection obligations apply to employee, supplier and customer data? | Privacy controls | Adviser guidance | Phase 2 |
| Q-29b | P | How often should access rights be reviewed? | Access review cadence | Decision | Phase 12 |
| Q-33 | H | Are supplier payments executed in the bank by a person and recorded here, or initiated by the system? | Payment scope (no banking credentials stored either way) | Decision | Phase 8 |
| Q-33b | P | How often are bank statements reconciled, and in what format can they be exported? | Reconciliation design | Sample statement file | Phase 9 |
| Q-34 | H | May data be hosted outside Nigeria (cloud), or must it stay on a local host? | Hosting decision | Decision | Phase 1/12 |
| Q-36 | P | Is MFA feasible for users (phones/email access)? | Security configuration | Decision | Phase 2 |

## 6. Evidence checklist (collect blank or redacted)

- [ ] Purchase request form
- [ ] Supplier quotation / proforma invoice (redacted)
- [ ] Purchase order (blank template)
- [ ] Delivery note / waybill (blank)
- [ ] Goods received note (blank)
- [ ] Supplier invoice sample (redacted)
- [ ] Customer invoice sample (redacted, or blank template)
- [ ] Receipt / payment voucher (blank)
- [ ] Project budget template and a redacted version
- [ ] Project register / cost report (redacted)
- [ ] Chart of accounts (current)
- [ ] Supplier and customer lists (structure only)
- [ ] Stock register or spreadsheet (structure only)
- [ ] Bank statement export (redacted)
- [ ] Approval memo/authority list, if one exists
- [ ] Tax registration certificates (numbers may be redacted)
- [ ] Any NRS/e-invoicing correspondence

## 7. Answer log

| ID | Answered by | Date | Answer summary | Recorded as decision |
| --- | --- | --- | --- | --- |
| — | — | — | No answers received yet | — |

Answers are recorded here and mirrored into the decision register with a label (CONFIRMED / PROPOSED / ASSUMPTION / UNRESOLVED). Nothing is implemented as policy until it carries a CONFIRMED label and a named approver.
