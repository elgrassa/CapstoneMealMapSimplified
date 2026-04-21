FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY README.md ./

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -e ".[dev]"

COPY src/ ./src/
COPY ai/ ./ai/
COPY backend/ ./backend/
COPY demo_ui/ ./demo_ui/
COPY monitoring/ ./monitoring/
COPY data/ ./data/
COPY fixtures/ ./fixtures/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
COPY Makefile ./

RUN python3 scripts/seed_demo.py || echo "Demo corpus will seed at first compose up"

ENV PYTHONPATH=/app:/app/src:/app/ai/week1-rag

EXPOSE 8001 8501 8502

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
