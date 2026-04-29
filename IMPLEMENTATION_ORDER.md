# PassportAI — Implementation Order

## 0. Project Goal

PassportAI is a contest-ready Digital Product Passport workflow for SMEs.

The product must help a small business move from:

```text
photo + product inputs + supplier/master-data evidence
→ reconciled product state
→ evidence audit
→ machine-readable DPP
→ human-readable passport
→ remediation report
→ cloud-hosted public passport URL
→ QR/data carrier
```

Core thesis:

```text
PassportAI does not invent compliance.
It extracts visible evidence with Gemma, asks the right evidence questions, and fails closed until the passport is defensible.
```

---

## 1. Non-Negotiable Architecture Rules

### 1.1 Pipeline ownership

- `PassportPipeline` is the only orchestrator.
- Shared state lives in `PipelineState`.
- Agents do not orchestrate other agents.
- UI, CLI, and scripts call `PassportPipeline`; they do not duplicate pipeline logic.

### 1.2 Source of truth

- `reconciled_domain_data` is the source of product truth.
- `passport_json` is an artifact, not the center of the pipeline.
- `passport.html` is a render artifact, not a source of product facts.
- `gap_report.html` is a remediation artifact, not a second auditor.

### 1.3 Generator and renderer boundaries

- `DPPGenerator` is deterministic and projection-only.
- `DPPGenerator` consumes `reconciled_domain_data` plus audit policy metadata.
- `PassportRenderer` renders `passport.html` from `passport.json`.
- `GapReportGenerator` renders `gap_report.html` from `DataAuditAgent` output.
- No renderer creates, changes, or validates product truth.

### 1.4 Agent boundaries

- Agents do not pass raw reasoning traces to each other.
- Agents output structured payloads only.
- LLM-backed agents may explain or classify within their ownership boundary.
- LLM-backed agents must not invent supplier facts, legal facts, document references, identifiers, or environmental values.
- Missing evidence remains missing.

### 1.5 Fail-closed rule

The system must fail closed when evidence is missing, weak, contradictory, or unsupported.

Allowed statuses:

```text
draft
not_ready
ready_with_gaps
registry_ready
published_to_cloud
```

Not allowed:

```text
publishable because the model guessed
compliant because text sounds plausible
carbon value estimated without evidence
document reference invented
```

---

## 2. Agent Execution Model

Each agent has a perspective. A perspective does not mean unrestricted LLM authority.

| Agent | Deterministic responsibility | Gemma responsibility |
| --- | --- | --- |
| `VisionAgent` | Normalize structured JSON into the agent contract | Analyze product photo |
| `RegulatoryConsultant` | Classify product category and sector profile using explicit supported categories/rules | Explain classification uncertainty and required evidence to the user |
| `LegalAgent` | Map category to required legal evidence, regulation references, and passport citations | Explain what legal evidence is missing and why it matters |
| `LCASpecialist` | Check whether sustainability/LCA data references are present | Explain where to get data and why unsupported estimates are unsafe |
| `GS1Specialist` | Check digit, identifier plausibility, resolver/data-carrier readiness | Optional wording only; default is deterministic |
| `DataAuditAgent` | Schema diff, readiness scoring, blocker policy, publishability decision | Human-readable feedback wording only |

## 2.1 Agent safety rules

### VisionAgent

Owns:

- visible evidence extraction
- visible category hints
- visible markings/certifications
- image-based uncertainty

Does not own:

- final regulatory category
- supplier-confirmed model/serial/country
- legal compliance
- publishability

Gemma mode:

- required for photo analysis
- structured output only
- no markdown
- no invented product facts

### RegulatoryConsultant

Owns:

- category and sector profile classification
- applicable evidence checklist
- classification uncertainty
- user-facing explanation of why a category/sector applies

Does not own:

- final legal compliance
- supplier evidence values
- passport publication decision

Gemma mode:

- optional for explanation
- deterministic classification remains preferred for supported demo categories
- if Gemma is used, output must be structured and enum-limited

### LegalAgent

Owns:

- legal evidence gap review
- required document/reference mapping
- regulation references to show in passport/report
- user-facing explanation of what legal evidence must be attached

Does not own:

- declaring the product compliant
- inventing declaration references
- inventing technical documentation

Gemma mode:

- may explain missing legal evidence
- must not claim official compliance

### LCASpecialist

Owns:

- sustainability evidence gap review
- carbon/recycled-content evidence requirements
- warnings against unsupported environmental claims

Does not own:

- generated carbon footprint values
- generated recycled-content values
- generated water/packaging metrics without evidence

Gemma mode:

- may explain where data comes from
- may explain why it matters
- must not calculate or invent LCA values

### GS1Specialist

Owns:

- product identifier checks
- operator/facility identifier checks
- resolver URL readiness
- QR/data-carrier readiness

Gemma mode:

- not required
- optional wording only, after deterministic checks

### DataAuditAgent

Owns:

- schema diff
- readiness score
- publishability
- blockers
- supplier requests
- where-to-get-data synthesis
- final audit policy

Gemma mode:

- wording only
- cannot change score
- cannot change verdict
- cannot add/remove gaps
- cannot create product facts

---

## 3. Artifact Model

The product must generate these user-visible artifacts.

```text
passport.json       machine-readable VCDM-shaped DPP
passport.html       human-readable Digital Product Passport
gap_report.html     remediation plan for SME
qr.png              QR code to the public passport URL
```

No `manifest.json` for the contest slice unless a later technical need appears.

Reason:

```text
manifest.json is optional package integrity infrastructure.
It is not necessary for the core demo and currently adds cognitive overhead.
```

## 3.1 Artifact responsibilities

### passport.json

Generated by:

```text
DPPGenerator
```

Purpose:

- machine-readable DPP
- VCDM-shaped wrapper
- DPP schema payload
- deterministic projection from reconciled state

Must not:

- contain raw reasoning traces
- contain duplicated `credentialSubject.dpp.dpp`
- become source of truth for audit

### passport.html

Generated by:

```text
PassportRenderer
```

Purpose:

- human-readable DPP
- product identity
- passport status
- identifiers
- data carrier
- sector-specific fields
- compliance evidence status
- technical appendix

Must not:

- recompute audit
- call agents
- invent missing values

### gap_report.html

Generated by:

```text
GapReportGenerator
```

Purpose:

- explain why passport is or is not ready
- explain blockers
- explain missing evidence
- explain supplier requests
- explain where to get missing data

Must not:

- read `passport_json` as source of audit truth
- call agents
- decide publishability

### qr.png

Generated after public URL is known.

Purpose:

- data carrier for physical product/packaging
- points to `passport.html` or resolver URL

Must not:

- point to a temporary cloud URL in cloud mode
- point to `localhost` in final cloud demo
- be generated before storage can provide the target URL

---

## 4. Implementation Phases

## BLOCK 1 — Stabilize Current Report and Passport Artifacts

### 1.1 Finish `gap_report.html` polish

Status:

```text
in progress / polish
```

Tasks:

- remove `Optional Blocking` and `Recommended Blocking` display
- show human owner labels
- show human publication blockers
- show human supplier request labels
- keep raw field paths only in technical details
- keep browser Save as PDF button
- keep no server PDF dependency

Definition of done:

```text
pytest tests/test_gap_report.py -q
pytest tests/test_dpp_generator.py -q
set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 && pytest tests/test_pipeline.py -q
```

Commit:

```text
polish: humanize gap report blockers and actions
```

### 1.2 Finish `passport.html`

Status:

```text
in progress
```

Tasks:

- ensure primary Jinja template renders, not fallback
- improve visual design
- use clean EU-style palette
- header: product name, status, readiness, QR placeholder/right side
- cards:
  - Identity
  - Data Carrier
  - Economic Operator
  - Sector Passport Data
  - Environmental / Circularity
  - Compliance
  - Evidence Readiness
  - Technical Appendix
- add print-friendly CSS
- add buttons:
  - View Gap Report
  - Download JSON
  - Save as PDF

Definition of done:

```text
pytest tests/test_passport_renderer.py -q
pytest tests/test_dpp_generator.py -q
pytest tests/test_gap_report.py -q
set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 && pytest tests/test_pipeline.py -q
```

Commit:

```text
feat: render human-readable passport artifact
```

---

## BLOCK 2 — Prompt Cleanup and Agent Contracts

Goal:

```text
Move prompts out of code where Gemma is actually used or planned.
Do not turn deterministic policy into LLM truth.
```

### 2.1 `prompts/vision_analysis.txt`

Runtime prompt.

Tasks:

- support categories:
  - `batteries`
  - `electrical_appliances`
  - `textiles`
  - `unknown`
- remove tote-bag-specific demo bias
- include example aligned with industrial battery schema if available
- require strict JSON
- require uncertainty
- forbid supplier/model/serial/country/legal facts unless visible

Definition of done:

- VisionAgent loads prompt from file
- structured output still validated
- live Gemma photo demo still works
- fake-client tests pass

### 2.2 `prompts/regulatory_classification.txt`

Runtime prompt only if `RegulatoryConsultant` uses Gemma for explanation or classification support.

Tasks:

- supported category explanations:
  - batteries: EU Battery Regulation context
  - electrical appliances: ESPR/RoHS context
  - textiles: ESPR/textile DPP context
- structured output:
  - product_group
  - sector_profile
  - confidence
  - classification_uncertainty
  - required_evidence_hints
  - user_explanation

Definition of done:

- classification remains enum-limited
- no free-form category creation
- no publishability decision

### 2.3 `prompts/legal_evidence_review.txt`

Runtime prompt only for legal evidence explanation.

Tasks:

- explain what evidence is missing
- map missing documents/references to category
- produce SME-readable action text

Hard limits:

- no compliance claim
- no declaration invention
- no document reference invention

### 2.4 `prompts/lca_evidence_review.txt`

Runtime prompt only for sustainability evidence explanation.

Tasks:

- explain where carbon/recycled/CRM data should come from
- explain why unsupported estimates are unsafe
- request supplier-backed evidence

Hard limits:

- no carbon footprint generation
- no recycled content generation
- no water/packaging values without evidence

### 2.5 `prompts/audit_explanation.txt`

Runtime prompt for optional `AuditNarrativeWrapper`.

Tasks:

- explain deterministic audit result to SME
- produce:
  - executive summary
  - why not publishable
  - top priorities explained
  - SME next-step explanation

Hard limits:

- cannot change readiness score
- cannot change verdict
- cannot add/remove gaps
- cannot create facts

### 2.6 No runtime `dpp_generation.txt`

Do not implement DPP generation through LLM.

Instead:

```text
docs/dpp_schema_mapping.md
```

Reason:

```text
DPPGenerator must remain deterministic and projection-only.
```

---

## BLOCK 3 — VisionAgent Hardening

Goal:

```text
Make the current Gemma-backed VisionAgent reliable and testable.
```

Tasks:

- prompt loaded from `prompts/vision_analysis.txt`
- response schema owned by VisionAgent, not hidden in generic client
- fake Gemma client tests
- invalid JSON fail-closed
- malformed structured output fail-closed
- unknown category handling
- no supplier/country/model hallucination
- no legal/compliance claims
- optional image resizing guidance/helper if needed

Definition of done:

```text
pytest tests/test_vision_agent.py -q
pytest tests/test_pipeline.py -q
live demo command works
```

Commit:

```text
test: harden gemma-backed vision agent
```

---

## BLOCK 4 — RegulatoryConsultant Readiness

Goal:

```text
Give the regulatory agent a real perspective without letting it create compliance truth.
```

Implementation choice:

```text
deterministic classification first
Gemma explanation optional
```

Tasks:

- categories:
  - batteries
  - electrical_appliances
  - textiles
- sector profiles:
  - battery passport profile
  - electrical appliance profile
  - textile profile
- output required evidence hints
- user-facing explanation may be Gemma-generated
- output structured payload only

Definition of done:

- supported category tests
- unknown category fail-closed
- no publishability decision
- no document facts invented

Commit:

```text
feat: add structured regulatory classification perspective
```

---

## BLOCK 5 — LegalAgent Readiness

Goal:

```text
LegalAgent gives legal evidence feedback, not legal certification.
```

Tasks:

- map category to evidence requirements
- produce missing legal evidence gaps
- include regulation references/citations for passport/report
- Gemma may explain what to add and why
- deterministic checks decide whether evidence is present

Hard limits:

- no “compliant” claim
- no declaration invention
- no technical documentation invention

Definition of done:

- battery legal evidence test
- electrical legal evidence test
- textile legal evidence test
- missing evidence stays missing

Commit:

```text
feat: add legal evidence review perspective
```

---

## BLOCK 6 — LCASpecialist Readiness

Goal:

```text
LCASpecialist explains environmental evidence needs without inventing metrics.
```

Tasks:

- remove/disable `gwp_coefficients.csv` logic if it estimates unsupported values
- check data presence:
  - carbon footprint reference
  - recycled content reference
  - critical raw materials reference
  - packaging/circularity evidence
- Gemma may explain:
  - where to get data
  - why it matters
  - what supplier document to request

Hard limits:

- no generated carbon values
- no generated recycled percentages
- no unsupported environmental claims

Definition of done:

- missing carbon data produces gap
- supplier-backed reference closes gap
- no numeric hallucination

Commit:

```text
feat: add sustainability evidence review perspective
```

---

## BLOCK 7 — GS1Specialist Readiness

Goal:

```text
Keep identifier and resolver checks deterministic.
```

Tasks:

- check product identifier presence
- check operator identifier presence
- check facility identifier presence
- check resolver URL availability
- check QR readiness once QR exists
- check-digit/plausibility logic where applicable
- optional human wording only

Definition of done:

- deterministic tests
- no LLM dependency required
- clear feedback for missing identifiers

Commit:

```text
test: harden identifier and resolver checks
```

---

## BLOCK 8 — DataAuditAgent and Audit Narrative

Goal:

```text
Keep deterministic audit policy, add optional human explanation wrapper.
```

### 8.1 Deterministic audit core

Tasks:

- schema diff
- readiness score
- blockers
- publishability
- supplier requests
- where-to-get-data
- optional/recommended gaps not displayed as direct blockers unless policy requires it

Definition of done:

- test score logic
- test blocker grouping
- test no optional direct blocker
- test all required gaps

### 8.2 AuditNarrativeWrapper

Tasks:

- load `prompts/audit_explanation.txt`
- input deterministic audit payload
- output human explanation only
- fail closed to deterministic fallback wording

Hard limits:

- cannot change score
- cannot change verdict
- cannot add/remove gaps
- cannot create facts

Commit:

```text
feat: add audit explanation wrapper
```

---

## BLOCK 9 — S3 Storage and Public URL Strategy

Goal:

```text
Make the DPP package publicly accessible.
```

Tasks:

- implement real `S3Storage`
- use boto3
- support:
  - `save_package`
  - `get_public_url`
  - `file_exists`
  - `delete_package`
- content types:
  - `.html` → `text/html`
  - `.json` → `application/json`
  - `.png` → `image/png`
- env config:
  - `STORAGE_MODE=local|s3`
  - `AWS_S3_BUCKET`
  - `AWS_REGION=eu-west-1`
  - `PUBLIC_BASE_URL`

Definition of done:

- local storage still default
- S3 mode uploads `passport.json`, `passport.html`, `gap_report.html`
- `storage.get_public_url(passport_id, "passport.html")` returns a stable URL
- credentials missing gives clear error

Commit:

```text
feat: publish passport artifacts to s3
```

---

## BLOCK 10 — QR Generator

Goal:

```text
Generate QR only after public passport URL is known.
```

Tasks:

- implement/finish `qr.py`
- generate `qr.png`
- target URL:
  - local mode: local passport URL
  - S3 mode: public cloud passport URL
- print-ready mode:
  - `box_size=15`
  - safe border
- add QR to `passport.html`
- add QR to artifact paths

Definition of done:

- QR opens `passport.html`
- local and S3 URL behavior tested
- pipeline does not generate QR before public URL strategy is known

Commit:

```text
feat: generate qr data carrier for passport url
```

---

## BLOCK 11 — Gradio UI

Goal:

```text
Let a non-developer run the workflow.
```

### 11.1 Layout

Three columns:

1. Input
   - image upload
   - product group
   - product name
   - brand
   - identifiers/evidence fields
   - storage mode

2. Progress
   - Vision
   - Regulatory
   - Legal
   - LCA
   - GS1
   - Audit
   - Passport
   - Cloud publish
   - QR

3. Output
   - passport.html link
   - gap_report.html link
   - passport.json download
   - QR preview
   - ZIP download

### 11.2 Execution

- `generate_dpp()` calls `PassportPipeline`
- yield progress by pipeline step
- no UI-side orchestration
- errors shown clearly

### 11.3 ZIP download

- package generated artifacts into ZIP
- works in local mode
- cloud links shown in S3 mode

Definition of done:

- non-developer can run end-to-end
- UI does not bypass pipeline
- UI output matches CLI output

Commit:

```text
feat: add gradio demo interface
```

---

## BLOCK 12 — Registry-Ready Semantics

Goal:

```text
Separate draft, cloud-published, and registry-ready states.
```

Statuses:

```text
draft
not_ready
ready_with_gaps
registry_ready
published_to_cloud
```

Rules:

`registry_ready` requires:

- required product identity fields present
- required identifiers present
- required operator data present
- required sector fields present
- required evidence references present
- stable public resolver URL
- no publication blockers
- validation passes
- human review status explicit

`published_to_cloud` requires:

- S3 upload succeeded
- public passport URL exists
- QR points to public URL

Not claimed:

```text
officially registered in EU registry
```

Definition of done:

- first-pass demo is `not_ready`
- second-pass demo with evidence can become `registry_ready`
- cloud mode can become `published_to_cloud`

Commit:

```text
feat: add registry-ready status semantics
```

---

## BLOCK 13 — Hero Scenario

Goal:

```text
Lock one demo story only after artifacts, agents, S3, QR, and UI are stable.
```

### 13.1 Scenario

Primary scenario:

```text
industrial battery / battery pack
```

First pass:

- photo + minimal inputs
- Gemma extracts visible evidence
- passport generated as draft
- audit says not ready
- gap report explains missing supplier/master-data evidence

Second pass:

- add structured evidence:
  - battery category
  - chemistry
  - operator identifier
  - product identifier
  - declaration reference
  - technical documentation reference
  - carbon footprint reference
- output:
  - registry_ready
  - passport.html
  - passport.json
  - gap_report.html
  - cloud URL
  - QR

Definition of done:

- canonical input image
- canonical UI flow
- canonical CLI fallback
- canonical output screenshots
- expected output documented
- no architecture changes after this block

Commit:

```text
docs: lock hero scenario
```

---

## BLOCK 14 — CLI Install

Goal:

```text
Let developers install and run PassportAI locally.
```

Tasks:

- `pyproject.toml`
- `src/cli.py`
- commands:
  - `passportai demo`
  - `passportai run`
  - `passportai ui`
- `.env.example`
- install instructions

Definition of done:

```text
pip install -e .
passportai demo ...
passportai ui
```

Commit:

```text
feat: add installable cli
```

---

## BLOCK 15 — Submission

### 15.1 README

Must include:

- what DPP is
- why SMEs need it
- why now
- architecture
- Gemma usage
- local setup
- cloud setup
- demo commands
- UI screenshots
- limitations

### 15.2 Writeup

Narrative:

```text
DPP compliance is coming.
SMEs lack affordable tooling.
PassportAI turns photos and evidence into registry-ready DPP packages.
Gemma provides bounded expert perspectives.
Deterministic audit prevents hallucinated compliance.
```

### 15.3 Video

Flow:

1. Problem
2. Why DPP matters
3. Upload product photo
4. Gemma extracts visible evidence
5. Draft passport generated
6. Gap report explains missing evidence
7. Add evidence
8. Registry-ready passport generated
9. Cloud URL + QR
10. Why Gemma matters

### 15.4 Final freeze

Allowed:

- bug fixes
- wording
- CSS polish
- prompt tightening
- README/writeup/video

Not allowed:

- new orchestrator
- new agent ownership
- schema redesign
- generator-first rewrite
- broad platform refactor

Commit:

```text
docs: prepare competition submission
```
