# PassportAI

PassportAI is a Python prototype for generating reviewable Digital Product Passport (DPP) packages from a product photo, product description, and optional product evidence. The current vertical slice focuses on a fail-closed demo flow: generate a draft passport, show missing evidence, block unsupported publication claims, optionally host the public `passport.html` page on S3, and generate a QR code pointing to the passport page.

The project is built around local Gemma/Ollama inference for vision-supported extraction and deterministic Python gates for regulatory, legal, sustainability, identifier, and audit checks. It is not a compliance guessing tool: missing or weak evidence is represented as gaps rather than silently converted into compliance claims.

## What it generates

For each run, PassportAI can create a local package under `output/<passport_id>/` containing:

| Artifact | Purpose |
| --- | --- |
| `passport.json` | Machine-readable DPP JSON/JSON-LD-style artifact generated from reconciled domain data. |
| `passport.html` | Human-readable public passport page. This is the only artifact intended for S3 public hosting in the current plan. |
| `gap_report.html` | User-facing remediation report explaining blockers, missing evidence, owners, and next actions. |
| `qr.png` | QR code targeting the human-readable passport URL. |
| `product_image.<ext>` | Product image copied into the generated package. |
| `passport_package.zip` | Local review/download bundle created by the Gradio UI flow. |

## Current capabilities

- Product photo + text intake through a Gradio workspace.
- Two runtime modes:
  - `demo_mock`: deterministic fixture vision output for reliable UI/demo runs.
  - `live_gemma`: Gemma-backed visual analysis through Ollama.
- Supported product groups in the current implementation:
  - `batteries`
  - `electrical_appliances`
  - `textiles`
- Multi-agent pipeline with explicit ownership boundaries:
  - `VisionAgent` for visible product evidence.
  - `RegulatoryConsultant` for product group and sector profile anchoring.
  - `LegalAgent` for document/legal evidence gaps.
  - `LCASpecialist` for sustainability/LCA evidence gaps.
  - `GS1Specialist` for identifier, resolver, and QR readiness checks.
  - `DataAuditAgent` for deterministic readiness verdicts and publication gating.
- DPP projection through `DPPGenerator`.
- Human-readable rendering through `PassportRenderer` and `GapReportGenerator`.
- Local storage and optional S3 storage.
- S3 public hosting rule: only `passport.html` is uploaded publicly by the pipeline for S3-style storage; JSON, gap report, QR image, and ZIP remain local review artifacts.

## Architecture

```text
Product photo + user input
        │
        ▼
VisionAgent / DemoVisionAgent
        │
        ▼
RegulatoryConsultant ── LegalAgent ── LCASpecialist ── GS1Specialist
        │                  │              │                │
        └──────────────────┴──────────────┴────────────────┘
                           │
                           ▼
              Reconciled domain data
                           │
                           ▼
                  DataAuditAgent
          readiness_score / readiness_verdict / is_publishable
                           │
                           ▼
                    DPPGenerator
                     passport.json
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
     PassportRenderer  GapReportGenerator  QRCodeGenerator
      passport.html      gap_report.html       qr.png
             │
             ▼
       LocalStorage or S3Storage
```

The key architectural constraint is separation of concerns. Agents produce bounded payloads; `PassportPipeline` reconciles those payloads; `DataAuditAgent` determines readiness; `DPPGenerator` projects the reconciled state into an artifact without inventing missing facts.

## Technology stack

- Python 3.11+
- Gradio for the web UI
- Ollama Python SDK for local Gemma calls
- Gemma model configured as `gemma4:e4b`
- Jinja2 for HTML templates
- qrcode + Pillow for QR generation
- boto3 / botocore for S3 publishing
- Pydantic, jsonschema, pyld for validation and structured data support
- pytest for tests
- Development tooling listed in `requirements.txt`: black, isort, mypy, ruff

## Installation

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create local configuration
cp .env.example .env
```

For live Gemma mode, install Ollama separately and pull the configured model:

```bash
ollama pull gemma4:e4b
```

Make sure Ollama is running before using `live_gemma` mode or `scripts/run_demo_passport.py`.

## Running the Gradio UI

The current working UI entry point is:

```bash
python scripts/run_gradio_app.py --host 127.0.0.1 --port 7860
```

Then open:

```text
http://127.0.0.1:7860
```

Recommended demo settings:

```text
Runtime Mode: demo_mock
Storage Mode: local
Product Group: batteries
Image: demo_images/product_small.jpg
```

Use `live_gemma` only when Ollama and the model are available locally.

## Running the CLI demo

The CLI demo is intended for Gemma-backed vision and requires Ollama:

```bash
python scripts/run_demo_passport.py \
  --image demo_images/product_small.jpg \
  --description "Photo-only battery product for DPP readiness demo" \
  --product-group batteries \
  --brand-name "Demo Brand" \
  --storage local \
  --timeout 600
```

For S3 mode, configure `.env` first and run with `--storage s3`.

## S3 publishing

Set the following values in `.env` for S3 mode:

```env
STORAGE_MODE=s3
AWS_REGION=eu-west-1
AWS_S3_BUCKET=your-bucket-name
AWS_S3_PREFIX=passports
PUBLIC_BASE_URL=
```

Credentials can come from AWS CLI/default credentials, IAM role, or environment variables. Do not commit `.env`.

Current publishing semantics:

```text
Readiness: audit verdict such as not_ready, ready_with_gaps, ready, or blocked_by_conflicts
Storage: local / s3
Package URL: public passport page URL when S3 is used
QR URL or local QR path: generated data-carrier artifact
```

S3 hosting does not prove compliance readiness. It only makes the public passport page reachable. The audit verdict controls whether publication should be considered supported.

## Project structure

```text
passportai_repo/
├── agents/                 # Agent contracts and agent implementations
├── contexts/               # JSON-LD context files
├── data/                   # Local coefficient/reference data
├── demo_images/            # Demo product image
├── output/                 # Generated local artifacts; should be cleaned before final submission unless examples are documented
├── prompts/                # Prompt files for agent tasks
├── schemas/                # DPP schema files
├── scripts/                # Gradio and CLI demo entry points
├── src/
│   ├── core/               # Pipeline, DPP generator, renderers, QR generator, Gemma client
│   ├── processing/         # Legacy/placeholder photo and QR processing modules
│   ├── storage/            # Local and S3 storage providers
│   ├── ui/                 # Gradio UI
│   └── utils/              # JSON-LD loading utilities
├── templates/              # Jinja2 HTML templates
├── tests/                  # pytest suite
├── FINAL_POLISH_PLAN.md    # Remaining polish plan
├── README.md               # Project documentation
└── requirements.txt        # Python dependencies
```

## Development status

According to `FINAL_POLISH_PLAN.md`, the core vertical slice is already working:

- agent pipeline
- `passport.json`
- `passport.html`
- `gap_report.html`
- S3 hosting for the public passport page
- QR code
- Gradio UI v1

Observed status in this archive:

- The final-plan test subset passes:
  - `pytest tests/test_gradio_app.py -q`
  - `pytest tests/test_pipeline.py -q`
  - `pytest tests/test_qr_generator.py -q`
  - `pytest tests/test_s3_storage.py -q`
  - `pytest tests/test_dpp_generator.py -q`
  - `pytest tests/test_passport_renderer.py -q`
  - `pytest tests/test_gap_report.py -q`
- The Gradio UI implements the readiness/storage separation required by the polish plan.
- `PassportPipeline` sends only `passport.html` to upload-only storage providers such as S3.
- The generated local review package still includes JSON, gap report, QR, image, and ZIP artifacts.
- `scripts/run_gradio_app.py` is the practical UI entry point.
- The repository contains generated `output/` examples and a `.env` file in the archive. These should be removed or sanitized before public submission.

## Remaining polish work

From `FINAL_POLISH_PLAN.md`, the main remaining work is submission hardening, not new architecture:

- Finish visual polish for the Gradio workspace if final screenshots still look too prototype-like.
- Keep polishing `passport.html` and `gap_report.html` for a credible demo video.
- Clean generated outputs, caches, empty files, and obsolete skeleton/docs that conflict with the current plan.
- Lock the battery hero scenario and add `docs/HERO_SCENARIO.md` plus screenshots under `demo_assets/screenshots/`.
- Record the final 3-minute demo video.
- Run the final test subset again after cleanup.

## Known limitations

- PassportAI does not certify legal compliance. It produces a draft passport and a deterministic evidence gap report.
- Missing evidence should block unsupported publication claims.
- The old root `README.md`, `aws_s3_setup.md`, `IMPLEMENTATION_ORDER.md`, and some comments still contain outdated wording from earlier architecture stages.
- Some schema files exist for product categories beyond the currently supported runtime product groups; do not present those categories as implemented until pipeline support is added.
- Full test-suite execution needs cleanup: `tests/test_agents.py` globally mocks `sys.modules["src"]`, which can break later test collection if tests are run together without isolation.

## License

The archive includes a `LICENSE` file and the previous README states Creative Commons Attribution 4.0 International (CC-BY 4.0). Verify final licensing text before public release.
