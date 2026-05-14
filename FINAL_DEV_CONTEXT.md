# PassportAI — Final Development Context

You are a senior Python architect and technical writer helping finish the PassportAI project.

## Project identity

PassportAI is a Python prototype for generating a Digital Product Passport package from:

- product image
- product description
- optional evidence / supporting material

The current goal is not to build a full production platform. The goal is to finish a clean, demo-ready vertical slice with a credible architecture, safe evidence handling, clear UI, stable tests, and professional documentation.

## Current architecture

The current architecture is:

```text
Gradio UI / demo script
→ PassportPipeline
→ agents
→ DPPGenerator
→ PassportRenderer
→ GapReportGenerator
→ QRGenerator
→ LocalStorage / S3Storage
```

The reliable user-facing entry point is:

```bash
python scripts/run_gradio_app.py
```

The project no longer uses or documents the obsolete FastAPI/rembg architecture.

Removed obsolete files:

```text
app.py
COPILOT_CONTEXT.md
src/server/
src/processing/
.vs/
```

Current important directories:

```text
agents/                  Agent implementations
prompts/                 Agent prompt templates
schemas/                 JSON schemas
scripts/                 Runtime scripts
src/core/                Main pipeline, rendering, QR, DPP generation
src/storage/             Local and S3 storage providers
src/ui/                  Gradio UI
templates/               HTML templates
tests/                   Test suite
output/.gitkeep          Keeps output directory without committing generated artifacts
```

## Important constraints

Do not reintroduce:

```text
FastAPI
Uvicorn
rembg
src/server
src/processing
gap_report.pdf
python app.py
```

The current project uses:

```text
gap_report.html
passport.html
passport.json
qr.png
product_image.<ext>
passport_package.zip
```

Cloud mode must publish only:

```text
passport.html
```

The full package should remain local/downloadable from the Gradio UI.

## Current cleanup status

A cleanup commit was created:

```text
chore: remove obsolete architecture files
```

The following validation subset passed after cleanup:

```bash
pytest tests/test_gradio_app.py -q
# 11 passed

pytest tests/test_pipeline.py tests/test_qr_generator.py tests/test_s3_storage.py tests/test_dpp_generator.py tests/test_passport_renderer.py tests/test_gap_report.py -q
# 47 passed
```

Use this subset as the reliable final-polish validation target.

Full `pytest -q` may still need separate test-isolation cleanup if legacy tests mutate global imports or monkeypatch `sys.modules`.

## Development branch strategy

Work should continue from `dev` after merging `cleanup/final-polish`, or from a new branch created from the cleaned state.

Recommended branch name:

```bash
feature/final-polish
```

Avoid vague branch names such as:

```text
dev-two
dev-final-final
```

## Final development goals

The final goal is a clean demo-ready project.

Priorities:

1. Make the Gradio demo path stable.
2. Ensure the pipeline produces all expected artifacts.
3. Ensure unsupported or insufficient evidence never becomes a confident compliance claim.
4. Improve agent prompts.
5. Improve UI wording and output clarity.
6. Keep docs consistent with the current architecture.
7. Keep tests passing.
8. Avoid adding large new architectural layers.

## Expected artifacts

For each generated passport package, the project should produce:

```text
passport.json
passport.html
gap_report.html
qr.png
product_image.<ext>
passport_package.zip
```

The ZIP package should include the generated local artifacts.

## Evidence and compliance philosophy

The system must be fail-closed.

If evidence is missing, weak, ambiguous, or unsupported:

- do not invent values
- do not claim compliance
- mark fields as missing, unknown, or requiring evidence
- surface gaps in `gap_report.html`
- keep the user-facing explanation clear

The project must not imply that it performs legally authoritative compliance certification.

Preferred wording:

```text
readiness
evidence coverage
gap report
unsupported claim
requires evidence
demo mode
not legal certification
```

Avoid overclaiming:

```text
certified compliant
legally verified
official DPP certification
guaranteed compliance
```

## Technology stack

Current stack:

```text
Python 3.11+
Gradio
Ollama / Gemma
Jinja2
qrcode
Pillow
boto3 / botocore
jsonschema
python-dotenv
httpx
pytest
```

Dependencies that should not be reintroduced unless architecture changes deliberately:

```text
fastapi
uvicorn
rembg
onnxruntime
weasyprint
python-multipart
```

## Important files to inspect before editing

Inspect these before making final changes:

```text
FINAL_POLISH_PLAN.md
README.md
requirements.txt
scripts/run_gradio_app.py
src/core/pipeline.py
src/core/dpp_generator.py
src/core/passport_renderer.py
src/core/gap_report.py
src/core/qr_generator.py
src/storage/local.py
src/storage/aws_s3.py
src/storage/base.py
src/ui/gradio_app.py
agents/
prompts/
schemas/
templates/
tests/test_gradio_app.py
tests/test_pipeline.py
tests/test_dpp_generator.py
tests/test_gap_report.py
```

## Agent prompt improvement plan

The `prompts/` directory and `agents/` directory need a focused audit.

The goal is not to make prompts longer. The goal is to make them stricter, safer, more schema-aligned, and more consistent with the fail-closed architecture.

### Step 1 — Inventory prompts and agent contracts

Inspect:

```text
prompts/
agents/
```

For each agent, identify:

- input data expected by the agent
- output format expected by downstream code
- whether output must be JSON
- whether the agent is allowed to infer missing values
- which fields must be evidence-backed
- which fields must be marked unknown if evidence is absent

Create a small internal map like:

```text
Agent name
→ prompt file
→ input contract
→ output contract
→ validation target
→ known risk
```

### Step 2 — Make prompts schema-aware

Every prompt that produces structured output should explicitly reference the expected JSON shape.

Prompt rules:

```text
Return valid JSON only.
Do not include Markdown.
Do not include explanatory text outside JSON.
Use null or "unknown" when evidence is missing.
Do not invent product facts.
Do not claim compliance without evidence.
Preserve uncertainty.
```

If the project has schema files in `schemas/`, prompts should align with those schemas.

### Step 3 — Add evidence discipline

Agent prompts should distinguish between:

```text
observed_from_image
provided_by_user
derived_from_evidence
inferred_low_confidence
missing
```

The final passport should not treat all fields equally. Evidence-backed fields are stronger than inferred fields.

For compliance-sensitive fields, the prompt should prefer:

```json
{
  "value": null,
  "status": "missing_evidence",
  "reason": "No supporting evidence was provided."
}
```

over invented values.

### Step 4 — Strengthen category-specific behavior

The runtime groups are:

```text
batteries
electrical_appliances
textiles
```

Prompts should not use the same compliance expectations for every product type.

Agent prompts should include product-group awareness:

```text
If product_group is "batteries", focus on battery-specific evidence gaps.
If product_group is "electrical_appliances", focus on electrical appliance evidence gaps.
If product_group is "textiles", focus on textile/material/care/recyclability evidence gaps.
```

But prompts must not hallucinate regulatory requirements beyond the data encoded in the project.

### Step 5 — Improve gap-report reasoning

Gap report prompts or logic should produce clear missing-evidence explanations.

Good gap item:

```text
Missing battery chemistry evidence. The uploaded description does not provide chemistry, capacity, safety documentation, or lifecycle evidence.
```

Bad gap item:

```text
Battery data incomplete.
```

Each gap should ideally include:

```text
field
severity
why it matters
missing evidence
recommended next evidence
```

### Step 6 — Improve claim language

Prompts should avoid absolute claims.

Replace risky phrasing:

```text
This product complies with DPP requirements.
```

with safer phrasing:

```text
The current evidence is sufficient to populate selected passport fields, but this demo does not provide legal compliance certification.
```

or:

```text
The available evidence is insufficient to support this claim.
```

### Step 7 — Add prompt regression tests if practical

Add lightweight tests that check:

- prompt files exist
- prompts contain fail-closed language
- prompts require JSON-only output where needed
- prompts prohibit unsupported compliance claims
- prompts mention missing evidence behavior

Example test intent:

```text
tests/test_prompts.py
```

Possible assertions:

```python
assert "Do not invent" in prompt
assert "valid JSON" in prompt
assert "missing evidence" in prompt.lower()
assert "compliance" in prompt.lower()
```

Do not overfit tests to huge prompt text. Test the critical safety constraints only.

## UI polish plan

The Gradio UI should make the current state obvious:

- demo/mock mode vs live Gemma mode
- local package vs S3 public URL
- readiness result
- gap report availability
- ZIP download
- QR meaning

The UI should not suggest that S3 uploads the full package if current architecture only publishes `passport.html`.

User-facing labels should be precise:

```text
Generate Passport Package
Download ZIP Package
Open Passport HTML
Open Gap Report
Readiness Status
Evidence Gaps
```

Avoid vague labels:

```text
Publish Everything
Certified Passport
Legal Compliance Result
```

## Documentation polish plan

README should stay aligned with the cleaned architecture.

README must document:

- project purpose
- features
- current stack
- installation
- Ollama setup
- `.env.example`
- Gradio launch command
- demo mode vs live mode
- generated artifacts
- S3 behavior
- project structure
- final development status
- known limitations

README must not document removed entry points or removed modules.

Also check:

```text
aws_s3_setup.md
FINAL_POLISH_PLAN.md
UI_SPEC_V1.md
```

If docs mention old cloud semantics, `gap_report.pdf`, FastAPI, rembg, or `app.py`, update them or archive them.

## Storage semantics

Local mode:

```text
Generate full package locally.
Expose ZIP via Gradio.
Do not require public hosting.
```

S3 mode:

```text
Upload/publish only passport.html.
Return public passport URL.
Generate QR to the public passport URL.
Keep full package local/downloadable.
```

Do not make S3 mode upload private evidence files unless that is explicitly added and tested.

## Testing requirements

After meaningful changes, run:

```bash
pytest tests/test_gradio_app.py -q
```

and:

```bash
pytest tests/test_pipeline.py tests/test_qr_generator.py tests/test_s3_storage.py tests/test_dpp_generator.py tests/test_passport_renderer.py tests/test_gap_report.py -q
```

Expected current result:

```text
11 passed
47 passed
```

If tests fail, prefer fixing the implementation or tests directly related to the change. Do not weaken tests just to make them pass.

## Code quality rules

Keep changes small and coherent.

Do not add a new framework unless necessary.

Do not reintroduce abandoned architecture.

Prefer explicit data contracts over implicit prompt behavior.

Prefer deterministic behavior in demo mode.

Do not silently swallow errors that affect generated artifacts.

Use clear names:

```text
passport_url
gap_report_path
package_zip_path
readiness_status
evidence_gaps
```

Avoid ambiguous names:

```text
result
data
thing
published_to_cloud
cloud_uploaded
```

## Final checklist

Before final submission:

- [ ] `git grep` finds no obsolete architecture terms:

```bash
git grep -n "FastAPI\|rembg\|gap_report.pdf\|src/processing\|src/server\|passport_server\|python app.py"
```

- [ ] Gradio test subset passes.
- [ ] Pipeline/render/storage test subset passes.
- [ ] README matches current architecture.
- [ ] Agent prompts are fail-closed and schema-aware.
- [ ] Gap report clearly explains missing evidence.
- [ ] UI labels do not overclaim compliance.
- [ ] `.env` is not committed.
- [ ] `output/` contains only `.gitkeep`.
- [ ] Generated artifacts are not committed.
- [ ] Demo flow can be run from a fresh checkout.

## Recommended next implementation order

1. Inspect and update agent prompts.
2. Add or update lightweight prompt tests.
3. Run test subset.
4. Polish Gradio UI wording.
5. Run test subset again.
6. Review README and docs for consistency.
7. Run final grep for obsolete terms.
8. Commit changes with a focused message.

Recommended commit message:

```text
feat: polish agent prompts and final demo flow
```

or, if mostly prompt/docs changes:

```text
chore: align prompts and docs with final architecture
```

## Practical commands for the next session

Create or switch to the final feature branch:

```bash
git checkout dev
git pull origin dev
git checkout -b feature/final-polish
```

Inspect prompts and agents:

```bash
Get-ChildItem prompts -Recurse
Get-ChildItem agents -Recurse
git grep -n "prompts/"
git grep -n "open(.*prompt\|read_text.*prompt\|PromptTemplate\|system_prompt\|user_prompt"
```

Validate obsolete architecture is still absent:

```bash
git grep -n "FastAPI\|rembg\|gap_report.pdf\|src/processing\|src/server\|passport_server\|python app.py"
```
