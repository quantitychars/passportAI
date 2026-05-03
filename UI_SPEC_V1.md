# PassportAI UI Spec v1

## 0. Purpose

PassportAI UI is a Digital Product Passport workspace for SMEs.

It must let a non-developer move from:

```text
product photo + product inputs + optional supplier/master-data evidence
→ generated passport.json
→ generated passport.html
→ generated gap_report.html
→ generated qr.png
→ optional S3 public URL
```

The UI must not become a second orchestrator.

```text
UI collects input.
UI calls PassportPipeline.
UI displays outputs.
UI does not call agents directly.
UI does not create product truth.
UI does not edit passport artifacts directly.
```

## 1. Product Positioning

The interface is not a generic chatbot. It is:

```text
Digital Product Passport workspace with a chat-like input surface.
```

The user should feel that they are preparing a regulated product passport, seeing what is missing, and publishing a generated package when ready.

## 2. Core UI Principles

### 2.1 Document-first

The generated `passport.html` is the primary human-facing artifact. Workspace actions such as export, S3 upload, QR generation, and download must be visually separate from the passport document.

### 2.2 Pipeline-first

Every generation action must go through:

```text
PassportPipeline.run(...)
```

The UI must not duplicate agent order, audit logic, DPP generation, QR generation, S3 upload, or artifact rendering.

### 2.3 Fail-closed UX

When generation fails, the UI must show a clear failure state and must not pretend that a valid passport exists.

Examples:

```text
VisionAgent failed because Gemma/Ollama could not load.
S3 upload failed because credentials are missing.
QR not generated because no public passport URL is available.
```

### 2.4 Explicit mode labeling

The UI may support:

```text
Live Gemma mode
Demo/mock mode
```

The active mode must always be visible. Demo/mock mode is allowed only for development and predictable demos. It must not be presented as a production compliance result.

## 3. Main Layout

The interface should feel like a clean AI workspace, not a generic LLM playground.

Recommended layout:

```text
Left: Conversation and input
Center/right: Artifact review workspace
Right rail: Actions and runtime settings
```

For Gradio v1:

```text
Row
  Column 35%: Chat/Input
  Column 65%: Preview/Artifacts
Optional right rail inside Preview column or as a narrow third column.
```

## 4. Empty State

Before the first run, the UI should show guidance instead of a blank workspace.

### 4.1 Empty-state guidance

Title:

```text
Create a Digital Product Passport
```

Sections:

#### How to ask

```text
Create a battery passport from this product photo.
Analyze this textile product and generate a gap report.
Generate a draft passport and tell me what is missing for publication.
Create a DPP package and publish it to S3.
```

#### What you can provide

```text
Product photo
Product group
Product name
Brand
Description
Identifier data
Supplier evidence references
Technical documentation references
Declaration of conformity reference
```

#### What PassportAI generates

```text
passport.html — human-readable Digital Product Passport
passport.json — machine-readable DPP credential
gap_report.html — remediation plan
qr.png — QR code to the public passport URL
```

### 4.2 Empty-state disappearance

The empty-state guidance disappears after the first generation starts and is replaced by progress, artifact preview, and run result.

## 5. Left Column: Conversation And Input

### 5.1 Chat-like input surface

The left side should contain:

```text
message history
image upload
product group selector
product name input
brand name input
description input
optional evidence expander
generate button
```

### 5.2 Required inputs

Minimum v1 required inputs:

```text
product image
product group
brand name
description
storage mode
runtime mode
```

Product group enum:

```text
batteries
electrical_appliances
textiles
```

Runtime mode enum:

```text
live_gemma
demo_mock
```

Storage mode enum:

```text
local
s3
```

### 5.3 Optional evidence inputs

These fields support second-pass improvement and registry-ready flow:

```text
Product identifier / GTIN
Operator identifier
Facility identifier
Resolver URL override
Battery category
Battery chemistry
Declaration of conformity reference
Technical documentation reference
Carbon footprint reference
Recycled content reference
Supplier evidence note
```

Do not require all of them for first-pass generation.

### 5.4 User message behavior

After generation, the user may submit supported update intents:

```text
update_product_name
update_brand_name
add_product_identifier
add_operator_identifier
add_facility_identifier
add_battery_category
add_battery_chemistry
add_declaration_reference
add_technical_documentation_reference
add_carbon_footprint_reference
add_recycled_content_reference
regenerate
```

Unsupported free-form mutations must be rejected or converted into guidance. The UI must not silently mutate product truth from vague chat text.

## 6. Progress Timeline

During generation, show operational pipeline events. Do not show raw agent reasoning.

Recommended event names:

```text
Preparing product input
Packaging product image
Running visual product analysis
Classifying regulatory product group
Checking legal evidence
Checking sustainability evidence
Checking identifiers and resolver readiness
Synthesizing audit result
Generating passport.json
Rendering passport.html
Rendering gap_report.html
Generating qr.png
Uploading artifacts to S3
Finalizing package
```

Event states:

```text
pending
running
completed
failed
skipped
```

Allowed notes:

```text
Gemma vision analysis is running.
S3 upload is disabled in local mode.
QR generation waits for the public passport URL.
Demo mode uses fixture vision output.
```

Not allowed:

```text
raw hidden reasoning
chain-of-thought style text
fake agent thoughts
unverified legal claims
```

## 7. Artifact Workspace

After a successful run, the workspace should show generated artifacts.

Tabs:

```text
Passport
Gap Report
JSON
QR
Run Summary
```

Default tab:

```text
if is_publishable == false:
    open Gap Report
else:
    open Passport
```

### 7.1 Passport tab

Shows:

```text
passport.html preview
Open in browser link
Save as PDF hint
```

The preview is not an editor.

### 7.2 Gap Report tab

Shows:

```text
gap_report.html preview
top blockers summary
supplier request summary
open in browser link
```

### 7.3 JSON tab

Shows:

```text
passport.json formatted preview
download button
```

Manual JSON editing is out of scope for v1.

### 7.4 QR tab

Shows:

```text
qr.png preview
target URL
download QR button
```

QR is enabled only after a valid target URL exists.

### 7.5 Run Summary tab

Shows:

```text
passport_id
storage_mode
package_url
qr_url
readiness_score
readiness_verdict
is_publishable
warnings
errors
```

## 8. Right Rail: Actions And Settings

### 8.1 Initial disabled actions

Before generation, these buttons are disabled:

```text
Open Passport
Open Gap Report
Download JSON
Download ZIP
Open Public URL
Push To S3
Generate QR
```

Disabled reason:

```text
Generate a passport first.
```

### 8.2 Enabled after successful run

```text
Open Passport — enabled if passport.html exists
Open Gap Report — enabled if gap_report.html exists
Download JSON — enabled if passport.json exists
Download ZIP — enabled if local artifacts exist
Open Public URL — enabled if package_url exists and is public
Generate QR — enabled if QR is not already generated and package_url exists
Push To S3 — enabled if local run exists and S3 config is present
```

### 8.3 S3 settings panel

Fields:

```text
AWS region
S3 bucket
S3 prefix
Public base URL
Access key ID
Secret access key
Session token
```

Security rules:

```text
Never display secret access key after input.
Never write credentials into generated artifacts.
Never include credentials in logs.
```

Prefer environment variables for normal use. In-session credentials may be supported for demos, but should not be persisted unless secure storage is implemented.

### 8.4 Storage mode behavior

Local mode:

```text
Artifacts are saved under output/<passport_id>/
No public URL is guaranteed.
QR may point to local package URL if configured.
```

S3 mode:

```text
Artifacts are staged locally.
Artifacts are uploaded to S3.
package_url points to public passport.html.
qr.png points to package_url.
```

## 9. State Model

Suggested UI state:

```python
{
    "has_started": bool,
    "is_running": bool,
    "runtime_mode": "live_gemma" | "demo_mock",
    "storage_mode": "local" | "s3",
    "latest_input": dict,
    "latest_result": dict | None,
    "artifact_paths": dict,
    "artifact_urls": dict,
    "messages": list,
    "progress_events": list,
    "errors": list,
    "warnings": list,
}
```

Do not store raw agent reasoning. Do not treat rendered artifacts as source of truth.

## 10. Generation Flow

### 10.1 First-pass flow

```text
User uploads image and product basics
User clicks Generate Passport
UI validates minimum inputs
UI calls PassportPipeline.run(...)
UI streams or simulates progress from known steps
Pipeline returns artifacts and audit result
UI displays result
```

### 10.2 Second-pass evidence flow

Preferred v1 interaction:

```text
Gap Report shows missing fields
User clicks Add Missing Evidence
Structured evidence form opens
User fills known evidence fields
User clicks Regenerate
Pipeline reruns from inputs/evidence
New artifacts replace previous run or create a new run
```

Do not directly patch `passport.html` or `passport.json`.

## 11. Demo Mode

Demo mode exists to keep UI development and judge demos stable when local Gemma/Ollama cannot run.

Always show:

```text
Demo mode: fixture vision output is used.
```

In demo mode:

```text
VisionAgent does not call live Gemma.
Photo analysis is deterministic fixture output.
Artifacts are for demonstration, not regulated evidence.
```

In live mode:

```text
VisionAgent uses Gemma/Ollama.
Gemma output is schema-validated.
Malformed output fails closed.
```

## 12. Error Handling

### 12.1 Ollama/Gemma failure

Show:

```text
Gemma vision analysis failed.
Reason: model could not load / timeout / invalid JSON.
You can retry, switch to demo mode, or reduce local memory pressure.
```

### 12.2 S3 failure

Show specific causes when available:

```text
AWS_S3_BUCKET is missing.
AccessDenied: uploader policy does not allow s3:PutObject.
Public URL returned AccessDenied: bucket policy or Block Public Access must be configured.
```

### 12.3 QR failure

Show:

```text
QR could not be generated because no valid public passport URL is available.
```

### 12.4 Partial artifact failure

If one artifact fails, do not show the run as fully successful.

Use:

```text
success = false
partial_artifacts = [...]
errors = [...]
```

## 13. Visual Direction

Use:

```text
light background
large calm spacing
strict cards
document-style typography
clear disabled states
subtle shadows
minimal color
```

Typography:

```text
Headings: Georgia or formal serif fallback
Body: Inter / Segoe UI / system sans
Labels: uppercase, letter-spaced, small, semibold
Values: medium/semibold
Technical values: monospace, wrapped safely
```

Avoid:

```text
overly colorful SaaS dashboard
fake AI thought bubbles
dense tables in the main passport view
buttons embedded in the document body
raw stack traces in user-facing UI
```

## 14. Files To Implement

Recommended first UI commit:

```text
src/ui/gradio_app.py
scripts/run_gradio_app.py
tests/test_gradio_app.py
docs/UI_SPEC_V1.md
```

Optional:

```text
src/ui/state.py
src/ui/mock_clients.py
```

Do not add database, auth, accounts, or history in v1.

## 15. Tests Required

Unit tests:

```text
empty state exists
artifact buttons disabled before run
storage mode validation
runtime mode validation
minimum input validation
pipeline is called exactly once
agents are not called directly by UI
successful pipeline result maps to artifact links
failed pipeline result maps to error state
demo mode is visibly labeled
```

Integration smoke:

```text
python scripts/run_gradio_app.py
```

Manual checks:

```text
upload image
select batteries
run local mode
open passport tab
open gap report tab
open JSON tab
open QR tab
download ZIP
run S3 mode
open public URL
```

## 16. Definition Of Done

BLOCK 11 is done when:

```text
A non-developer can open the UI, upload a product photo, fill product basics,
run the pipeline, and receive passport.html, gap_report.html, passport.json,
qr.png, and cloud links when S3 mode is enabled.
```

Hard requirements:

```text
UI calls PassportPipeline only.
UI does not call agents directly.
UI does not create product facts.
UI shows demo/live mode explicitly.
Artifact actions are disabled until artifacts exist.
Errors are shown clearly.
Generated artifacts match CLI output.
```

## 17. Future Work

Not part of v1:

```text
user accounts
auth
database
passport history
CloudFront setup
custom domains
NFC writing
multi-product workspace
direct JSON editor
free-form natural-language mutation of all DPP fields
```

These can be documented as future production roadmap, not contest-critical implementation.

## 18. Current Next Step

Implement:

```text
src/ui/gradio_app.py
scripts/run_gradio_app.py
tests/test_gradio_app.py
```

Keep the first UI commit narrow:

```text
chat-like input
pipeline call
progress display
artifact tabs
disabled/enabled action rail
local and s3 mode support
explicit demo/live mode label
```
