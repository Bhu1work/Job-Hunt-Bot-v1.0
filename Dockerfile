# ── Base image: Playwright's official Python image has all Chromium deps ──────
# This saves ~300MB vs installing browser deps manually on python:slim
FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

# Keep Python output unbuffered (so logs appear in real-time)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Install Python dependencies first (cached layer) ─────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Install Playwright browser (Chromium only — smaller than full install) ────
RUN playwright install chromium

# ── Copy project source ───────────────────────────────────────────────────────
COPY . .

# ── Create runtime directories (volumes will overlay these) ──────────────────
RUN mkdir -p data logs applications assets credentials \
             resumes/generated Resume

# ── Default: show help (override with `docker compose run bot python main.py ...`) ──
CMD ["python", "main.py", "--help"]
