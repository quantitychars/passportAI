# PassportAI — Final Polish Plan

## Context

Current date: 13 May. Internal submission deadline: 17 May evening.

The project already has the core vertical slice:

- agent pipeline
- passport.json
- passport.html
- gap_report.html
- S3 public hosting
- QR code
- Gradio UI v1

The remaining work is not broad feature development. It is submission hardening: make the demo reliable, visually credible, easy to understand, and easy to judge.

---

## Final Rule

Do not add new architecture unless it directly improves the final demo.

Allowed:

- UI polish
- passport.html polish
- gap_report.html polish
- cleanup
- README/writeup/video
- small status semantics fix
- bug fixes

Not allowed:

- new database
- auth/accounts
- CloudFront
- NFC writing
- new orchestrator
- broad schema redesign
- new product categories
- free-form chat editing
- full registry API integration

---

## Priority Order

## P0 — Freeze Current Working State

Goal: preserve a rollback point before polish.

Tasks:

- ensure Gradio UI tests pass
- ensure pipeline/QR/S3/passport/gap tests pass
- commit working UI v1

Commands:

```cmd
pytest tests/test_gradio_app.py -q
pytest tests/test_pipeline.py -q
pytest tests/test_qr_generator.py -q
pytest tests/test_s3_storage.py -q
pytest tests/test_dpp_generator.py -q
pytest tests/test_passport_renderer.py -q
pytest tests/test_gap_report.py -q
```

Commit:

```cmd
git add src/ui/gradio_app.py scripts/run_gradio_app.py tests/test_gradio_app.py docs/UI_SPEC_V1.md
git commit -m "feat: add gradio demo interface"
```

Definition of done:

- current UI can launch
- local demo mode works
- current code is committed

---

## P1 — Minimal Readiness / Cloud Status Semantics

Goal: prevent S3 upload from looking like compliance readiness.

Decision:

- remove `published_to_cloud` as a passport readiness status
- keep cloud upload as technical metadata

Readiness statuses:

```text
draft
not_ready
ready_with_gaps
registry_ready
```

Cloud metadata:

```text
storage_mode
cloud_uploaded
storage_provider
package_url
qr_url
```

Invariant:

```text
registry_ready unlocks publishing.
S3 upload produces package_url.
package_url does not prove readiness.
```

Tasks:

- update implementation docs
- update UI wording
- update run summary wording
- ensure passport/gap report do not imply official registration
- optionally add minimal test that cloud upload does not change readiness

Definition of done:

- UI shows readiness separately from cloud/package URL
- README/video wording uses “registry-ready package”, not “officially registered”
- no `published_to_cloud` shown as passport readiness

Suggested commit:

```cmd
git commit -m "docs: clarify readiness and cloud publication semantics"
```

---

## P2 — UI Visual Polish Block

Goal: make the Gradio UI look credible in a demo video.

Current issues:

- too much vertical scrolling
- helper content repeats in preview area
- workspace tools look like wide grey prototype bars
- orange accent feels like default Gradio
- first screen feels functional but not premium
- action state needs clearer language

Tasks:

1. Layout polish
   - keep left input column compact
   - keep right artifact workspace visible above the fold
   - reduce duplicated helper content
   - use a clean document/workspace layout

2. Empty state polish
   - show guidance only before first run
   - in artifact tabs before generation, show short placeholders:
     - “Passport preview will appear here after generation.”
     - “Gap report will appear here after generation.”
     - “QR code will appear here after generation.”

3. Action rail polish
   - make disabled actions visually lighter
   - show a clear hint: “Generate a passport first.”
   - after generation, show concise artifact actions

4. Color/typography polish
   - reduce orange accent
   - use navy/black/green palette
   - use more restrained buttons
   - keep document-like typography

5. Gradio warning fix
   - Gradio 6 moved `css` from `Blocks(...)` to `launch(...)`
   - current code has `css=_ui_css()` inside `gr.Blocks(...)`
   - remove `css=_ui_css()` from Blocks or accept the warning if moving CSS destabilizes launch
   - do not prioritize this over demo stability

Definition of done:

- `pytest tests/test_gradio_app.py -q` passes
- UI launches
- screenshot looks presentable for video
- no duplicate large empty-state cards in tabs

Suggested commit:

```cmd
git commit -m "polish: refine gradio demo workspace"
```

---

## P3 — Passport HTML Polish

Goal: make the human-readable passport look like a trustworthy document.

Checklist:

- product photo loads correctly
- QR section is visible when QR exists
- buttons are separated from passport document content
- readiness label is clear but not misleading
- field labels are human-readable
- raw technical paths only appear in technical appendix
- print/save-as-PDF mode works
- no “officially registered” or “certified compliant” language
- status says draft/not ready when evidence is missing
- document looks premium enough for video

Definition of done:

- `pytest tests/test_passport_renderer.py -q`
- open generated `passport.html` in browser
- screenshot is video-ready

Suggested commit:

```cmd
git commit -m "polish: improve human-readable passport presentation"
```

---

## P4 — Gap Report Polish

Goal: make the remediation plan useful to a non-expert SME.

Checklist:

- top section clearly says why publication is blocked
- blockers are human-readable
- owner labels are human-readable
- supplier request pack is clear
- “where to get data” section is practical
- action plan has obvious next steps
- raw DPP paths are pushed into technical detail sections
- optional/recommended items do not look like hard blockers unless policy requires it

Definition of done:

- `pytest tests/test_gap_report.py -q`
- gap report answers:
  1. Why can’t I publish?
  2. What do I need to add?
  3. Where do I get it?

Suggested commit:

```cmd
git commit -m "polish: clarify gap report actions for SMEs"
```

---

## P5 — Project Cleanup

Goal: remove confusion before judges or reviewers inspect the repo.

Do remove:

- `__pycache__`
- `.pytest_cache`
- old generated output folders, unless used as documented examples
- empty files
- abandoned old skeleton files that are not imported
- obsolete architecture drafts if they conflict with current plan

Do not remove:

- prompts
- tests
- templates
- current scripts
- docs needed to explain the system
- demo assets
- schemas

Safe commands:

```cmd
rmdir /s /q .pytest_cache
for /d /r . %d in (__pycache__) do @if exist "%d" rmdir /s /q "%d"
```

Before removing source files:

```cmd
git grep "filename_or_symbol"
```

Definition of done:

- repo tree is understandable
- tests still pass
- no obvious dead architecture files remain

Suggested commit:

```cmd
git commit -m "chore: clean up obsolete project files"
```

---

## P6 — Hero Scenario Lock

Goal: define one stable demo story.

Hero scenario:

```text
Battery product
→ photo + minimal input
→ draft DPP package
→ gap report blocks unsupported publication
→ S3 public passport URL
→ QR code opens passport.html
```

Required artifacts:

- screenshot of UI input
- screenshot of generated passport
- screenshot of gap report
- screenshot of QR tab / public URL
- public S3 links
- canonical command or UI steps

Files to create:

```text
docs/HERO_SCENARIO.md
demo_assets/screenshots/
```

Definition of done:

- demo can be repeated without improvisation
- video script can follow the scenario exactly

Suggested commit:

```cmd
git commit -m "docs: lock hero demo scenario"
```

---

## P7 — README / Writeup

Goal: make the project understandable without a live explanation.

README must include:

- what Digital Product Passport is
- why SMEs need this
- why now
- what PassportAI does
- how Gemma is used
- why the system is fail-closed
- local setup
- S3 setup
- UI run command
- demo scenario
- limitations
- screenshots

Key wording:

```text
PassportAI is not a compliance guessing tool.
Gemma extracts visible evidence and supports human-readable explanations.
Deterministic audit gates prevent unsupported compliance claims.
```

Definition of done:

- README has one clear quickstart
- judges can run or understand the demo from README

Suggested commit:

```cmd
git commit -m "docs: prepare project readme for submission"
```

---

## P8 — Video

Goal: produce a clear 3-minute competition video.

Suggested structure:

```text
0:00–0:25 Problem
0:25–0:50 Product
0:50–1:40 Demo flow
1:40–2:15 Gap report / fail-closed safety
2:15–2:40 S3 + QR
2:40–3:00 Impact + Gemma value
```

Must show:

- UI
- generated passport
- gap report
- QR/public URL
- explanation of Gemma role
- fail-closed audit

Do not over-explain code.

Definition of done:

- video exported
- captions or clear narration
- no broken links or visible stack traces

---

## P9 — Final Freeze

Allowed:

- bug fixes
- wording
- screenshots
- README
- video export
- final test run

Not allowed:

- new agents
- new storage providers
- schema redesign
- new UI architecture
- new registry integration

Final test run:

```cmd
pytest tests/test_gradio_app.py -q
pytest tests/test_pipeline.py -q
pytest tests/test_qr_generator.py -q
pytest tests/test_s3_storage.py -q
pytest tests/test_dpp_generator.py -q
pytest tests/test_passport_renderer.py -q
pytest tests/test_gap_report.py -q
```

---

## Daily Schedule

## 13 May

- commit UI v1
- create final polish plan
- apply minimal readiness/cloud wording update
- start UI visual polish

## 14 May

- finish UI visual polish
- polish passport.html
- polish gap_report.html

## 15 May

- project cleanup
- lock hero scenario
- README/writeup first draft

## 16 May

- record video
- edit video
- capture final screenshots

## 17 May

- final tests
- final README/writeup
- submit
- no new features

---

## Current Next Action

1. Commit current Gradio UI v1.
2. Implement minimal readiness/cloud semantics wording.
3. Start UI visual polish block.
