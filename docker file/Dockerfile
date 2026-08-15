# connector-auth-service Dockerfile
#
# This service is the OAuth connector authorization layer (Google, Spotify,
# LinkedIn) — see connector-authorization.md. It's a DIFFERENT service from
# agent-service and has different dependencies (requests-oauthlib,
# python-dotenv). Do not mix Dockerfiles/requirements.txt between the two —
# that mismatch is exactly what caused the ModuleNotFoundError on Render.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Render assigns its own $PORT at runtime — must bind to it, not a
# hardcoded port (same fix already applied to agent-service's Dockerfile).
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",8000)}/connect/status', timeout=3)" || exit 1

# Shell form so ${PORT} actually expands at container start.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
