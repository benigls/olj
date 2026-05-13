FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY olj_scraper ./olj_scraper
COPY ingest.py validate_ingestion.py run_alerts.py ./

CMD ["uv", "run", "python", "run_alerts.py"]
