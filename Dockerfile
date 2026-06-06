# ── Base image ──────────────────────────────────────
FROM python:3.11-slim

# ── System deps (needed for Pillow / WeasyPrint) ────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ───────────────────────────────
WORKDIR /app

# ── Install dependencies (pip, runtime only) ────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy source ─────────────────────────────────────
COPY . .

# ── Runtime environment ─────────────────────────────
ENV GRADIO_HOST=0.0.0.0
ENV GRADIO_PORT=7860
ENV OLLAMA_HOST=http://host.docker.internal:11434

# ── Persistent output volume ─────────────────────────
VOLUME /app/output

# ── Expose Gradio port ───────────────────────────────
EXPOSE 7860

# ── Entry point ──────────────────────────────────────
CMD ["python", "scripts/run_gradio_app.py", \
     "--host", "0.0.0.0", "--port", "7860"]