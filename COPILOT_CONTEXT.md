# PassportAI — Copilot Context

## One-line description

PassportAI generates ESPR-compliant Digital Product Passports (DPP) from a product photo + description using Gemma 4 E4B via Ollama, running 100% offline.

## Tech Stack

- Model: Gemma 4 E4B (gemma4:e4b) via Ollama (local, no cloud)
- UI: Gradio (localhost:7860)
- API: FastAPI (localhost:8000)
- Photo processing: rembg (background removal, 800x800 white bg)
- Storage: local files OR AWS S3 eu-west-1 (pluggable via .env)
- Validation: pyld (JSON-LD), EU VIES API (VAT)
- Output: JSON-LD VCDM 2.0 (Level 2), HTML page, QR code, Gap Report PDF

## Project Structure (flat view)

```
app.py                          # Entry point: starts Gradio + FastAPI
src/core/gemma_client.py        # Ollama wrapper: # generate(), think(),
                                    analyze_image(), call_tool(), _parse_json_fallback()
src/core/dpp_generator.py       # JSON-LD VCDM 2.0 passport builder
agents/vision_agent.py          # Photo → product attributes via Gemma 4 vision
                                    (extends BaseAgent)
src/core/gap_report.py          # Compliance gap analysis → PDF
src/processing/photo.py         # rembg background removal → 800x800 PNG
src/processing/qr.py            # QR code generation (LAST step, needs URL)
src/storage/base.py             # Abstract StorageProvider interface
src/storage/local.py            # Local file storage implementation
src/storage/aws_s3.py           # AWS S3 eu-west-1 implementation
src/server/passport_server.py   # FastAPI: GET /{uuid}, GET /{uuid}/photo
src/ui/gradio_app.py            # Gradio UI with progress bar
agents/base_agent.py            # BaseAgent: run() [abstract],
                                    call_tool(),run_verified_task(),_parse_json_fallback()
agents/regulatory_consultant.py # ESPR category + required fields
agents/legal_agent.py           # DoC, REACH, RoHS, VAT verification
agents/lca_specialist.py        # GWP/LCA estimation from BOM
agents/data_audit_agent.py      # Field completeness + consistency check
agents/gs1_specialist.py        # GTIN validation, DID:web, GS1 Digital Link
prompts/vision_analysis.txt     # Prompt: image → product attributes JSON
prompts/dpp_generation.txt      # Prompt: attributes → JSON-LD passport
prompts/gap_check.txt           # Prompt: passport → missing fields + actions
prompts/lca_assessment.txt      # Prompt: BOM → GWP estimate
prompts/legal_review.txt        # Prompt: passport → compliance flags
prompts/regulatory_classification.txt  # Prompt: product → ESPR category
prompts/data_audit.txt          # Prompt: passport → consistency check
schemas/universal_dpp.json      # Base DPP schema (all categories)
schemas/textile_dpp.json        # Textile-specific fields
schemas/battery_dpp.json        # Battery-specific fields
schemas/electronics_dpp.json    # Electronics-specific fields
schemas/furniture_dpp.json      # Furniture-specific fields
schemas/footwear_dpp.json       # Footwear-specific fields
contexts/w3c_credentials_v2.jsonld   # Cached W3C context (offline support)
contexts/schema_org.jsonld           # Cached schema.org context
contexts/gs1_voc.jsonld              # Cached GS1 vocabulary
templates/passport.html.jinja2  # Visual passport HTML template
templates/gap_report.html.jinja2 # Gap report HTML template
output/{uuid}/passport.json     # Generated DPP (JSON-LD Level 2)
output/{uuid}/photo.png         # Standardized photo (800x800 white bg)
output/{uuid}/passport.html     # Human-readable passport page
output/{uuid}/gap_report.pdf    # Compliance gap report
output/{uuid}/qr.png            # QR code (generated LAST after URL known)
```

## Agent Pipeline (12 steps, in order)

```
1.  Input validation + UUID generation + output/{uuid}/ creation
2.  Vision Agent → product attributes JSON          (parallel with step 3)
3.  Photo Agent (rembg) → photo.png                 (parallel with step 2)
4.  Merge: vision_output + user_input → unified_product_data
5.  Regulatory Consultant Agent → ESPR category + required_fields
6.  DPP Generator Agent → passport.json draft (JSON-LD Level 2)
7.  Legal Agent → compliance flags + missing_docs
8.  LCA Specialist Agent → GWP estimate (if not provided)
9.  Data Audit Agent → readiness_score + inconsistencies
10. GS1 Specialist Agent → product_id + passport_url
11. Gap Report Generator → gap_report.pdf
12. Storage Handler → save all files (local or S3)
13. QR Generator → qr.png using confirmed passport_url  ← ALWAYS LAST
```

## Key Data Types

### ProductInput

```python
image_path: str
description: str
gtin: str | None          # Optional: GS1 GTIN-14
certificates: list[str]   # Optional: paths to PDF certs
storage_mode: str         # "local" | "s3"
hosting_url: str | None   # Custom URL if self-hosted
```

### PassportPackage

```python
passport_id: str          # UUID
passport_json: dict       # Full JSON-LD VCDM 2.0
passport_url: str         # Public URL (local server or S3)
photo_path: str
html_path: str
qr_path: str
gap_report_path: str
readiness_score: int      # 0-100
```

### DPPReadinessScore

```python
essential_fields: int     # max 60 points
recommended_fields: int   # max 25 points
documents_attached: int   # max 10 points
photo_standardized: int   # max 5 points
total: int                # 0-100
```

## Critical Rules for Copilot

1. QR is generated LAST — it needs passport_url which is only known after storage
2. GemmaClient.analyze_image() uses Ollama multimodal (images parameter)
3. All agents use call_tool() for structured output. \_parse_json_fallback() is automatic fallback — never call manually. RegulatoryConsultant and LegalAgent use run_verified_task() (two-phase: think→call_tool).
4. Storage is pluggable — never hardcode S3 or local paths
5. Contexts are cached in contexts/ for offline mode — never fetch at runtime
6. Content hash = SHA-256 of credentialSubject JSON (sorted keys)
7. VIES API for VAT verification: only works for EU-registered legal entities
8. Model name in Ollama: gemma4:e4b
9. Ollama server must be running before app.py starts
10. All file I/O uses pathlib.Path, not string paths
11. Use call_tool() for structured output, run_verified_task() for regulatory agents

# \_parse_json_fallback() lives in BaseAgent as fallback — never call manually

## Key Functions Reference

### GemmaClient (src/core/gemma_client.py)

```python
client = GemmaClient(model="gemma4:e4b", host="http://localhost:11434")
text   = client.generate(prompt: str) -> str
text   = client.think(prompt: str) -> str                                    # reasoning mode (think=True)
text   = client.analyze_image(image_path: str, prompt: str) -> str          # multimodal vision
data   = client.call_tool(prompt: str, tools: list[dict], system_prompt: str | None) -> dict  # native function calling
data   = client._parse_json_fallback(raw: str) -> dict                      # fallback: parse JSON from text
```

### DPP Generator (src/core/dpp_generator.py)

```python
gen = DPPGenerator(gemma_client)
passport = gen.generate_from_text(description: str) -> dict
passport = gen.generate_from_photo_and_text(image_path: str, description: str) -> dict
merged   = gen.merge_inputs(vision_output: dict, user_input: dict) -> dict
valid, errors = gen.validate(passport: dict) -> tuple[bool, list]
```

### StorageProvider (src/storage/base.py)

```python
# Abstract interface — both local and S3 implement this
url = provider.save_package(passport_id: str, files: dict[str, Path]) -> str
url = provider.get_public_url(passport_id: str, filename: str) -> str
```

### BaseAgent (agents/base_agent.py)

```python
agent = SomeAgent(gemma_client)
result = agent.run(**kwargs) -> dict        # abstract
data   = agent.call_tool(prompt: str, tools: list[dict]) -> dict            # native function calling
data   = agent.run_verified_task(prompt: str, tools: list[dict]) -> dict   # two-phase: think→call_tool
data   = agent._parse_json_fallback(raw: str) -> dict                      # fallback only
```

## JSON-LD VCDM 2.0 Structure

```json
{
  "@context": ["https://www.w3.org/ns/credentials/v2", "..."],
  "id": "did:web:passportai.example.com:passports:{uuid}",
  "type": ["VerifiableCredential", "DigitalProductPassport"],
  "issuer": "did:web:passportai.example.com",
  "validFrom": "2025-04-13T00:00:00Z",
  "validUntil": "2035-04-13T00:00:00Z",
  "contentHash": "sha256:{hex}",
  "credentialSubject": { ... }
}
```

## Environment Variables (.env)

```
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma4:e4b
STORAGE_MODE=local                  # "local" | "s3"
LOCAL_OUTPUT_DIR=./output
AWS_REGION=eu-west-1
AWS_S3_BUCKET=passportai-passports
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
HOSTING_URL=http://localhost:8000   # used to build passport_url
GRADIO_PORT=7860
FASTAPI_PORT=8000
VIES_API_URL=https://ec.europa.eu/taxation_customs/vies/services/checkVatService
```

## ESPR Category → Schema Mapping

```
textiles      → schemas/textile_dpp.json
batteries     → schemas/battery_dpp.json
electronics   → schemas/electronics_dpp.json
furniture     → schemas/furniture_dpp.json
footwear      → schemas/footwear_dpp.json
chemicals     → schemas/chemicals_dpp.json
(default)     → schemas/universal_dpp.json
```

## Dependencies (key packages)

```
ollama>=0.2.0          # Python SDK for Ollama
fastapi>=0.110.0       # REST API server
gradio>=4.26.0         # Web UI
rembg>=2.0.56          # Background removal
Pillow>=10.3.0         # Image processing
pyld>=2.0.4            # JSON-LD processing
qrcode[pil]>=7.4.2     # QR code generation
jinja2>=3.1.3          # HTML templating
weasyprint>=62.0       # HTML → PDF
boto3>=1.34.0          # AWS S3 client
python-dotenv>=1.0.1   # .env loading
uvicorn>=0.29.0        # ASGI server for FastAPI
zeep>=4.2.1            # SOAP client for VIES API
```

## Error Handling Patterns

```python
# Always wrap Ollama calls
try:
    response = client.generate(prompt)
except ollama.ResponseError as e:
    # Ollama server down or model not found
    raise RuntimeError(f"Ollama error: {e}") from e

# Preferred: use call_tool() — returns dict directly, no manual parsing needed
data = agent.call_tool(prompt, tools)

# Fallback only (if model returns plain text instead of tool_calls):
# data = agent._parse_json_fallback(raw)
```

## File Naming Conventions

```
output/{uuid}/passport.json      ← never rename
output/{uuid}/photo.png          ← always PNG, always 800x800
output/{uuid}/passport.html      ← human-readable
output/{uuid}/gap_report.pdf     ← compliance gaps
output/{uuid}/qr.png             ← last generated
```
