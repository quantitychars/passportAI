# PassportAI

> Generate ESPR-compliant Digital Product Passports from a product photo + description — 100% offline, powered by Gemma 4 12B.

<!-- TODO: Add demo GIF here (30-second screen recording of full flow) -->
<!-- ![PassportAI Demo](docs/demo.gif) -->

## What is a Digital Product Passport?

The EU's [Ecodesign for Sustainable Products Regulation (ESPR)](https://ec.europa.eu/commission/presscorner/detail/en/ip_22_2013) requires most physical products sold in the EU to have a **Digital Product Passport (DPP)** — a machine-readable document containing:

- Material composition and origin
- Carbon footprint and sustainability data
- Repairability and durability information
- End-of-life instructions
- Certifications and compliance documents

**The problem:** Professional DPP consulting costs €15,000–€30,000 per product. With 6M+ SMEs in the EU needing compliance by 2027, that's a €90B+ barrier to market access.

**PassportAI:** Upload a product photo + description. Get a compliant DPP package in 6–9 minutes. Free. Offline. No data leaves your machine.

## Quick Start

```bash
# 1. Install Ollama and pull the model
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma4:12b-q4_k_m

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start PassportAI
python app.py
# → UI: http://localhost:7860
# → API: http://localhost:8000
```

## Architecture

```
Photo + Description
        │
        ▼
┌───────────────────────────────────────────────────────┐
│                    PassportAI Pipeline                 │
│                                                       │
│  ┌──────────────┐    ┌──────────────────────────┐    │
│  │ Vision Agent │    │      Photo Agent          │    │
│  │ (Gemma 4)    │    │   (rembg → 800x800 PNG)  │    │
│  └──────┬───────┘    └────────────┬─────────────┘    │
│         └──────────┬──────────────┘                  │
│                    ▼                                  │
│         ┌─────────────────────┐                      │
│         │   Merge & Enrich    │                      │
│         └──────────┬──────────┘                      │
│                    ▼                                  │
│  ┌──────────────────────────────────────────────┐    │
│  │  Regulatory  │  Legal   │ LCA Specialist │   │    │
│  │  Consultant  │  Agent   │    Agent       │   │    │
│  └──────────────┴──────────┴────────────────┘   │    │
│                    ▼                                  │
│         ┌─────────────────────┐                      │
│         │   DPP Generator     │ → passport.json      │
│         │  (JSON-LD VCDM 2.0) │                      │
│         └──────────┬──────────┘                      │
│                    ▼                                  │
│  ┌──────────────────────────────────────────────┐    │
│  │  Data Audit Agent → readiness_score (0-100)  │    │
│  └──────────────────────────────────────────────┘    │
│                    ▼                                  │
│         ┌─────────────────────┐                      │
│         │   Gap Report PDF    │ → gap_report.pdf      │
│         └──────────┬──────────┘                      │
│                    ▼                                  │
│         ┌─────────────────────┐                      │
│         │  Storage Handler    │ → local or S3        │
│         └──────────┬──────────┘                      │
│                    ▼                                  │
│         ┌─────────────────────┐                      │
│         │   QR Generator      │ → qr.png (LAST)      │
│         └─────────────────────┘                      │
└───────────────────────────────────────────────────────┘
```

## Output

For each product, PassportAI generates:

| File | Description |
|------|-------------|
| `passport.json` | JSON-LD VCDM 2.0 Level 2 Digital Product Passport |
| `photo.png` | Standardized 800×800 PNG with white background |
| `passport.html` | Human-readable HTML passport page |
| `gap_report.pdf` | Compliance gap analysis with action items |
| `qr.png` | QR code linking to the passport URL |

## Output Example

<!-- TODO: Add screenshot of passport.json and QR code -->

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key settings:
- `OLLAMA_MODEL` — model name (default: `gemma4:12b-q4_k_m`)
- `STORAGE_MODE` — `local` or `s3`
- `HOSTING_URL` — public URL for QR code generation

## API

```bash
# Generate a DPP
POST http://localhost:8000/generate
Content-Type: multipart/form-data
  photo: <file>
  description: "Cotton tote bag, made in Ukraine"
  gtin: "05901234123457"  # optional

# Retrieve a passport
GET http://localhost:8000/{uuid}           # passport.json
GET http://localhost:8000/{uuid}/photo     # photo.png
GET http://localhost:8000/{uuid}/html      # passport.html
```

## Supported Product Categories (ESPR)

- Textiles (🧵 implemented)
- Electronics (🔌 in progress)
- Batteries (🔋 planned)
- Furniture (🪑 planned)
- Footwear (👟 planned)
- Chemicals (⚗️ planned)

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) with `gemma4:12b-q4_k_m` pulled
- 8GB+ RAM (16GB recommended for Gemma 4 12B)
- GPU recommended but not required (CPU inference: ~3-5 min/passport)

## License

[Creative Commons Attribution 4.0 International (CC-BY 4.0)](LICENSE)

You are free to use, modify, and distribute this work for any purpose, including commercially, as long as you give appropriate credit.

---

Built for the [Kaggle Gemma Sprint 2025](https://www.kaggle.com/competitions/gemma-sprint-2025) competition.
