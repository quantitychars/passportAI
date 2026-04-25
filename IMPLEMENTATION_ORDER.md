# PassportAI — Revised Implementation Order

## Phase 0 — Baseline status

### Already completed / materially advanced

- `PassportPipeline` is the only orchestrator
- boundary-clean agent contract is established
- `DataAuditAgent` is implemented as cross-agent evidence auditor
- `validation.py` is aligned to the new audit contract
- `DPPGenerator` is refactored toward projection-only generation
- pipeline backbone is centered on `reconciled_domain_data`, not on `passport_json`
- pipeline and audit tests already exist for the new backbone

## Core rule for the rest of the build

No new abstractions unless they directly improve:

- demo reliability
- submission quality
- auditability
- schema compliance
- speed of integration

No new “platform” work before the vertical slice is complete.

---

## Phase 1 — Must-finish engineering before 30.04

### Goal

Ship a **stable end-to-end contest slice** that is demoable and test-backed.

### 1. Packaging integration

**Target date: 26–27.04**

Implement `_run_packaging_step()` so that it:

- calls the new `DPPGenerator.generate_from_reconciled_state(...)`
- stores `passport_json` in `PipelineState`
- performs generator validation
- produces a stable artifact output path for the DPP JSON

**Definition of done**

- pipeline run returns `passport_json`
- `passport_json` is generated from `reconciled_domain_data`, not from raw agent outputs
- no old generator-first flow remains in pipeline

---

### 2. DPPGenerator test coverage

**Target date: 27.04**

Create `tests/test_dpp_generator.py` covering:

- generation from reconciled state
- draft vs issued behavior
- derivation trace presence
- injected `now`
- basic `validate()`
- `validate_with_jsonschema()` success/failure paths

**Definition of done**

- `pytest tests/test_dpp_generator.py -v` passes
- generator behavior is locked against regressions

---

### 3. GapReportGenerator implementation

**Target date: 27–28.04**

Implement `GapReportGenerator` from `audit_result`, not from raw agent outputs and not from rendered DPP.

It must clearly answer:

- what is missing
- why it matters
- what blocks publication
- where the data should come from
- what the SME should do next

**Definition of done**

- report is generated from `DataAuditAgent` output
- report is readable by non-expert SME
- report distinguishes missing / weak / unverified / blocking issues

---

### 4. Full vertical slice test

**Target date: 28.04**

Add one integration test for:

`image/input -> pipeline -> reconciled_domain_data -> audit -> passport_json -> gap_report`

**Definition of done**

- one pipeline test proves end-to-end generation of both core artifacts
- no manual hidden steps required

---

### 5. Minimal artifact strategy

**Target date: 28–29.04**

Decide and implement the minimum artifact outputs needed for the demo:

- DPP JSON
- Gap Report HTML or Markdown
- optional local package folder
- optional QR placeholder only if already cheap and stable

**Definition of done**

- artifacts are saved deterministically
- demo can show real files, not only console output

---

### 6. Hero scenario lock

**Target date: 29.04**

Freeze one primary demo scenario:

- ideally **photo-only / weak-evidence first pass**
- then stronger second pass after added evidence

This becomes the single source of truth for:

- demo
- writeup
- screenshots
- video
- submission wording

**Definition of done**

- one canonical input set
- one canonical expected output set
- one canonical before/after story

---

### 7. Code freeze on architecture

**Target date: 30.04**

After this date:

- no new major abstractions
- no strategy-pattern rewrites
- no broad reordering of agents
- no new “platformization”

Only:

- bug fixes
- reliability
- polish
- submission material

---

## Phase 2 — Contest hardening and submission work (30.04–17.05)

### Goal

Maximize score on judging dimensions without destabilizing the build.

### 8. Demo hardening

**Target date: 30.04–03.05**

Focus on:

- deterministic demo path
- stable timing
- understandable outputs
- no flaky steps
- no manual hidden fixes during demo

**Definition of done**

- you can run the same demo multiple times with predictable result
- you know exactly which outputs/screens to show

---

### 9. Submission-grade UX polish

**Target date: 02.05–05.05**

Only small polish:

- labels
- report wording
- artifact naming
- screenshots
- visual clarity of outputs

Not allowed:

- architecture rewrites
- new agent responsibilities
- scope-expanding features

---

### 10. Writeup draft

**Target date: 04.05–07.05**

Write the Kaggle writeup early, not at the end.

It must clearly cover:

- the real-world problem
- why SMEs struggle with DPP/circular-product compliance
- where Gemma 4 is actually used
- architecture overview
- why the system is safe against invented facts
- one hero demo workflow
- current limitations
- future direction

**Definition of done**

- complete first draft exists
- not just notes
- can already be edited down to final submission

---

### 11. Video script and storyboard

**Target date: 06.05–09.05**

Prepare the 3-minute video before recording.

Structure:

1. problem in one sharp sentence
2. hero input
3. first-pass draft passport
4. gap report
5. second-pass improvement
6. why Gemma 4 matters
7. why this matters for EU circular-product transition / SME enablement

**Definition of done**

- exact script
- exact screen sequence
- exact spoken lines
- exact outputs to show

---

### 12. Public repo cleanup

**Target date: 08.05–10.05**

Make repo submission-ready:

- clear README
- architecture diagram if cheap
- setup instructions
- how to run demo
- what Gemma 4 does in the stack
- known limitations

**Definition of done**

- someone external can understand the project quickly
- repo reads like a product, not like private dev history

---

### 13. Video recording + first cut

**Target date: 10.05–12.05**

Record early enough to redo if needed.

**Definition of done**

- one full cut exists
- can be reviewed critically
- no reliance on one perfect take

---

### 14. Final polish window under exam constraints

**Target date: 12.05–17.05**

This is the exam-safe zone.

Only:

- bug fixes
- script tightening
- video trimming
- writeup tightening
- cover image / screenshots
- final run-throughs

Not allowed:

- major code refactor
- new subsystem
- new agent
- schema redesign

---

### 15. Submission freeze

**Target date: 17.05**

Everything public-facing should already be ready by then, one day before the official deadline on 18 May 2026, 23:59 UTC.

**Definition of done**

- repo public and clean
- demo works
- writeup finalized
- video finalized
- artifacts exported
- backup copy exists

---

## Phase 3 — Explicitly out of scope before submission

Do **not** add these before the contest is submitted unless a critical dependency forces it:

- sector strategy/plugin refactor
- broad Pydantic rewrite of the whole codebase
- cloud/HSM signing infrastructure
- self-correction loop orchestration
- broad multi-category platformization
- speculative scalability architecture

These are post-submission improvements, not pre-submission necessities.

---

## Final success criteria

### By 30.04

- one stable end-to-end working system exists

### By 17.05

- one strong story, one strong demo, one strong repo, one strong writeup, one strong video exist

Winning depends not only on code quality, but on how clearly the project demonstrates real impact, technical rigor, and why Gemma 4 is essential.
