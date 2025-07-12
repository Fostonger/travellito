FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install fonts with Cyrillic support and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    fonts-dejavu \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Refresh font cache
RUN fc-cache -f -v

COPY alembic.ini .
COPY migrations/ ./migrations/

COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 8000
# Simple container-level health-check. FastAPI answers quickly.
HEALTHCHECK CMD curl -f http://localhost:8000/healthz || exit 1
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000"]