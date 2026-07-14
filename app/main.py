"""
FastAPI application entrypoint.

Run with: uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.db.database import init_db
from app.logging_config import configure_logging
from app.rate_limiting import limiter

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once on startup: ensure the SQLite schema exists before any
    # request can hit the notes tool.
    await init_db()
    yield
    # (no teardown needed yet — placeholder for closing shared clients
    # if/when we add a pooled httpx.AsyncClient in a later phase)


app = FastAPI(
    title="Jarvis",
    description="A tool-calling AI agent backend.",
    version="0.1.0",
    lifespan=lifespan,
)

# Wire up rate limiting: attach the shared Limiter instance so route-level
# @limiter.limit(...) decorators (see app/api/routes.py) work, and register
# the handler that turns a limit breach into a clean 429 response instead
# of an unhandled exception.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(router)


@app.get("/health")
async def health() -> dict:
    """Basic liveness check, deliberately unauthenticated — hosting
    platforms (e.g. Render) poll this to confirm the instance is up, and
    shouldn't need an API key to do so."""
    return {"status": "ok"}
