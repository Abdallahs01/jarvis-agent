FROM python:3.11-slim

WORKDIR /app

# Install dependencies before copying app code so Docker can cache this
# layer -- code changes won't force a full dependency reinstall on every
# rebuild, only requirements.txt changes will.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# SQLite file lives inside the container at this path by default. On a
# single free-tier instance (no persistent volume) this resets on every
# redeploy -- acceptable for a demo; a real deployment would mount a
# volume here or swap SQLite for a managed Postgres/Render Disk.
ENV DATABASE_PATH=/app/data/jarvis.db
RUN mkdir -p /app/data

EXPOSE 8000

# Render (and most PaaS hosts) inject a $PORT env var and expect the
# server to bind to it; default to 8000 for plain local `docker run`.
# Shell form is required here so the ${PORT:-8000} substitution happens.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
