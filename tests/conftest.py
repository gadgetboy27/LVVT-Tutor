import os

# Must be set before app.core.config is first imported: module-scoped fixtures
# (e.g. the e2e TestClient) start the app lifespan before any function-scoped
# monkeypatch runs, and the PDF refresh loop would otherwise hit the real network
# and rewrite pdf_cache/ and the vector store.
os.environ["PDF_REFRESH_ENABLED"] = "false"
os.environ["BOOTSTRAP_ENABLED"] = "false"   # no background loading of shipped data into test DBs

import pytest


@pytest.fixture(autouse=True)
def _no_live_llm(monkeypatch):
    """Keep the suite deterministic even when a real ANTHROPIC/OPENAI key is
    present in .env (pydantic loads .env regardless of unset env vars). Force
    both providers 'not ready' so AI-backed code paths use their deterministic,
    non-AI fallbacks during tests."""
    try:
        from app.services.rag import ai_service
        monkeypatch.setattr(ai_service, "_anthropic_ready", lambda: False)
        monkeypatch.setattr(ai_service, "_openai_ready", lambda: False)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _no_pdf_refresh_loop(monkeypatch):
    """The startup PDF freshness loop does network I/O; keep it off in tests."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "PDF_REFRESH_ENABLED", False)
