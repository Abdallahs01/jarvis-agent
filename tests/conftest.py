"""
Shared pytest fixtures.
"""
import pytest

from app.config import get_settings

# Used by tests that hit /chat directly (test_api_chat.py) to build the
# X-API-Key header — kept here so it stays in sync with the env var set
# below rather than duplicated as a magic string in every test file.
TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def _test_settings(monkeypatch, tmp_path):
    """
    Every test gets a dummy Anthropic key, a dummy static API key, and its
    own isolated SQLite file (so tests never touch a real .env or a
    shared database).

    get_settings() is wrapped in @lru_cache, so without clearing it here
    the first test to call it would "pin" its settings for the rest of
    the test session, and later tests' monkeypatched env vars would be
    silently ignored.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))

    # Strip any ambient proxy env vars from the host machine. Tests should
    # be deterministic regardless of the developer's network setup, and
    # httpx (used by the weather tool) will otherwise try to route through
    # whatever proxy happens to be configured in this shell.
    for var in ("all_proxy", "ALL_PROXY", "http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
        monkeypatch.delenv(var, raising=False)

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """
    The rate limiter's in-memory counters live at module scope (see
    app/rate_limiting.py) and would otherwise carry usage over between
    tests, making one test's request count affect another's. Reset
    before and after every test so each one starts with a clean quota.
    """
    from app.rate_limiting import limiter

    limiter.reset()
    yield
    limiter.reset()
