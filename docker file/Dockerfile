# connector-auth-service Dockerfile

FROM python:3.12-slim

RUN apt-get update \
  && apt-get install -y python3-venv \
  && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create venv and make it the default Python
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 appuser \
  && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get('\"'\"'PORT'\"'\"',8000)}/connect/status', timeout=3)" || exit 1

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
