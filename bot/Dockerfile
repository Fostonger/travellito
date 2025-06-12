FROM python:3.12-slim

# Install system deps (curl for Docker HEALTHCHECKs)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

EXPOSE 8080
# Simple container-level health-check similar to web service
HEALTHCHECK CMD curl -f http://localhost:8080/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8080"]