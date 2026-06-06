# Installation Guide

This guide covers everything you need to run PassportAI locally — from a quick demo with no AI setup required, to a full live mode with Ollama and optional S3 publishing.

---

## Prerequisites

| Tool | Required | Notes |
|---|---|---|
| Python 3.11+ | Yes | [python.org/downloads](https://www.python.org/downloads/) |
| Git | Yes | [git-scm.com](https://git-scm.com/) |
| Docker | No | Only for the container setup path |
| Ollama | No | Only for `live_gemma` mode |

---

## Option A — Quick Start (no Ollama needed)

This is the fastest way to get the UI running. It uses pre-built fixture data instead of a live model, so no GPU or Ollama installation is required.

**1. Clone the repository**

```bash
git clone https://github.com/quantitychars/passportAI.git
cd passportAI
```

**2. Create and activate a virtual environment**

```bash
python -m venv .venv
```

On macOS / Linux:
```bash
source .venv/bin/activate
```

On Windows (PowerShell):
```powershell
.venv\Scripts\Activate.ps1
```

**3. Install dependencies**

```bash
pip install -r requirements-dev.txt
```

**4. Create your local configuration**

```bash
cp .env.example .env
```

The default values in `.env` work for local demo mode — no edits needed to get started.

**5. Start the Gradio UI**

```bash
python scripts/run_gradio_app.py
```

**6. Open the app**

```
http://127.0.0.1:7860
```

**Recommended demo settings:**

| Field | Value |
|---|---|
| Runtime Mode | `demo_mock` |
| Storage Mode | `local` |
| Product Group | `batteries` |
| Image | `demo_images/product_small.jpg` |

Click **Generate Passport** — you will get a full passport package with `passport.html`, `gap_report.html`, and a QR code, all generated from fixture data without any model calls.

---

## Option B — Docker Setup

Use this if you prefer containers over a local Python environment.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

**1. Build the image**

```bash
docker build -t passportai .
```

**2. Start the container**

```bash
docker-compose up
```

**3. Open the app**

```
http://localhost:7860
```

> **Note:** `demo_mock` mode works out of the box inside the container. For `live_gemma` mode, Ollama must be running on your host machine — the container connects to it automatically via `host.docker.internal`.

---

## Option C — Live Gemma Mode (requires Ollama)

Use this mode to run real visual analysis on product images using a local Gemma model.

**1. Install Ollama**

Download and install from [ollama.com](https://ollama.com/).

**2. Pull the model**

```bash
ollama pull gemma4:e4b
```

This downloads the model (~a few GB). You only need to do this once.

**3. Make sure Ollama is running**

Ollama starts automatically after installation on most systems. You can verify it:

```bash
ollama list
```

You should see `gemma4:e4b` in the list.

**4. Start PassportAI and switch to live mode**

Start the app using either the Quick Start or Docker instructions above, then in the UI change:

```
Runtime Mode → live_gemma
```

> **Note:** Live mode makes real model calls, which take longer than demo mode. A timeout of 600 seconds is set by default.

---

## Environment Variables

Your `.env` file controls runtime behaviour. All options are documented in `.env.example`. The key variables are:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | URL where Ollama is running |
| `OLLAMA_MODEL` | `gemma4:e4b` | Model name to use for vision and text tasks |
| `OLLAMA_TIMEOUT` | `600` | Seconds to wait for a model response |
| `STORAGE_MODE` | `local` | `local` saves files to disk; `s3` uploads to AWS S3 |
| `LOCAL_OUTPUT_DIR` | `./output` | Where generated passport packages are saved |
| `HOSTING_URL` | `http://localhost:8000` | Base URL used to build QR code links in local mode |
| `GRADIO_PORT` | `7860` | Port the Gradio UI listens on |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `USE_MOCK_OLLAMA` | `false` | Set `true` to skip all model calls (CI / offline testing) |

> **Never commit your `.env` file.** It is listed in `.gitignore` and may contain credentials.

---

## S3 Publishing (optional)

PassportAI can upload the public passport page (`passport.html`) to an AWS S3 bucket and generate a QR code pointing to it.

Set `STORAGE_MODE=s3` in your `.env` and configure the AWS variables.

For full bucket creation and IAM policy instructions, see [docs/s3_bucket_setup.md](docs/s3_bucket_setup.md).

---

## Running Tests

```bash
pytest tests/ -q
```

Ollama integration tests are skipped by default. To include them:

```bash
SKIP_OLLAMA_TESTS=false pytest tests/ -q
```
