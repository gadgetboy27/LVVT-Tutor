"""Tests for PDF url backfill + PDF viewer serving.

Runs entirely against in-memory SQLite with a fake ChromaDB collection, so it
needs neither Postgres nor a real vector store nor network access:

    python -m pytest tests/test_pdf_backfill_and_view.py -v

Covers the full chain:
  seed standard (no pdf_url) -> backfill_pdf_urls() pulls pdf_url from Chroma
  metadata -> /api/pdf/view hashes that url to pdf_cache/<md5[:8]>.pdf and serves
  it with cache + range headers, redirecting to source on a cache miss.
"""
import os

# database.py builds the engine from DATABASE_URL at import time, so it must be a
# valid URL before any app module is imported. We never use this engine (the
# tests inject their own SQLite engine), it just has to parse.
os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL") or "sqlite://"

import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.quiz import Standard
from app.api import pdf_viewer, quiz
from app.services.rag import pdf_indexer

PDF_URL = (
    "https://www.lvvta.org.nz/documents/operating_requirements_schedule/"
    "LVVTA_Operating_Requirements_Schedule_Chapter_3_LVV_Certification_Categories.pdf"
)


class FakeCollection:
    """Stand-in for a ChromaDB collection: maps standard_number -> pdf_url."""

    def __init__(self, mapping):
        self._mapping = mapping

    def get(self, where=None, include=None, limit=None):
        std = (where or {}).get("standard_number")
        url = self._mapping.get(std)
        if not url:
            return {"metadatas": []}
        return {"metadatas": [{"standard_number": std, "pdf_url": url}]}


@pytest.fixture
def TestingSessionLocal():
    # A single shared in-memory DB (StaticPool) so the request thread and the
    # test thread see the same tables and rows.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield SessionLocal
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed(SessionLocal, **kwargs):
    db = SessionLocal()
    db.add(Standard(**kwargs))
    db.commit()
    db.close()


# --------------------------------------------------------------------------- #
# backfill_pdf_urls
# --------------------------------------------------------------------------- #
def test_backfill_sets_pdf_url_from_chroma_metadata(TestingSessionLocal, monkeypatch):
    _seed(TestingSessionLocal, standard_number="ORS_Chapter_3", title="ORS Ch 3", pdf_url=None)
    _seed(TestingSessionLocal, standard_number="NOT_INDEXED", title="Unknown", pdf_url=None)
    _seed(TestingSessionLocal, standard_number="HAS_URL", title="Already", pdf_url="https://existing/x.pdf")

    fake = FakeCollection({"ORS_Chapter_3": PDF_URL})
    monkeypatch.setattr(pdf_indexer, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(pdf_indexer, "get_chroma_client", lambda: object())
    monkeypatch.setattr(pdf_indexer, "get_or_create_collection", lambda client: fake)

    result = pdf_indexer.backfill_pdf_urls()

    assert result["updated"] == 1
    assert result["checked"] == 2  # HAS_URL is skipped before the lookup
    assert result["unresolved"] == ["NOT_INDEXED"]

    db = TestingSessionLocal()
    assert db.query(Standard).filter_by(standard_number="ORS_Chapter_3").first().pdf_url == PDF_URL
    # a standard with no Chroma metadata is left untouched...
    assert db.query(Standard).filter_by(standard_number="NOT_INDEXED").first().pdf_url is None
    # ...and an already-populated url is never overwritten.
    assert db.query(Standard).filter_by(standard_number="HAS_URL").first().pdf_url == "https://existing/x.pdf"
    db.close()


# --------------------------------------------------------------------------- #
# /api/pdf/view
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(TestingSessionLocal, tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_viewer, "PDF_CACHE_DIR", str(tmp_path))

    app = FastAPI()
    app.include_router(pdf_viewer.router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_view_serves_cached_pdf_with_cache_and_range_headers(client, TestingSessionLocal, tmp_path):
    _seed(TestingSessionLocal, standard_number="ORS_Chapter_3", title="ORS Ch 3", pdf_url=PDF_URL)
    # The indexer caches as md5(pdf_url)[:8].pdf — write a file there.
    cache_name = hashlib.md5(PDF_URL.encode()).hexdigest()[:8] + ".pdf"
    (tmp_path / cache_name).write_bytes(b"%PDF-1.4\n%fake pdf body\n")

    resp = client.get("/api/pdf/view/ORS_Chapter_3")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "inline" in resp.headers["content-disposition"]
    assert "max-age" in resp.headers["cache-control"]
    assert resp.headers["accept-ranges"] == "bytes"
    assert resp.content.startswith(b"%PDF")


def test_view_supports_range_requests(client, TestingSessionLocal, tmp_path):
    _seed(TestingSessionLocal, standard_number="ORS_Chapter_3", title="ORS Ch 3", pdf_url=PDF_URL)
    cache_name = hashlib.md5(PDF_URL.encode()).hexdigest()[:8] + ".pdf"
    (tmp_path / cache_name).write_bytes(b"%PDF-1.4\n%fake pdf body\n")

    resp = client.get("/api/pdf/view/ORS_Chapter_3", headers={"Range": "bytes=0-3"})

    # Starlette's FileResponse honours Range -> 206 Partial Content.
    assert resp.status_code == 206
    assert resp.content == b"%PDF"


def test_view_redirects_to_source_when_uncached_and_download_fails(client, TestingSessionLocal, monkeypatch):
    _seed(TestingSessionLocal, standard_number="ORS_Chapter_4", title="ORS Ch 4", pdf_url="https://src/ch4.pdf")
    # No cached file and the lazy download fails -> must redirect, not 500/JSON.
    monkeypatch.setattr(pdf_viewer, "download_pdf", lambda url: None)

    resp = client.get("/api/pdf/view/ORS_Chapter_4", follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "https://src/ch4.pdf"


def test_view_lazily_downloads_and_caches_on_miss(client, TestingSessionLocal, tmp_path, monkeypatch):
    _seed(TestingSessionLocal, standard_number="ORS_Chapter_5", title="ORS Ch 5", pdf_url="https://src/ch5.pdf")
    monkeypatch.setattr(pdf_viewer, "download_pdf", lambda url: b"%PDF-1.4\n%downloaded\n")

    resp = client.get("/api/pdf/view/ORS_Chapter_5")

    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")
    # It should now be cached on disk under the url hash for next time.
    cache_name = hashlib.md5(b"https://src/ch5.pdf").hexdigest()[:8] + ".pdf"
    assert (tmp_path / cache_name).exists()


def test_view_404_for_unknown_standard(client):
    assert client.get("/api/pdf/view/DOES_NOT_EXIST").status_code == 404


# --------------------------------------------------------------------------- #
# deterministic quiz fallback
# --------------------------------------------------------------------------- #
def test_fallback_quiz_is_deterministic_and_on_topic(TestingSessionLocal):
    db = TestingSessionLocal()
    db.add(Standard(standard_number="LVVTA_STD_Braking_Systems", title="Braking Systems",
                    category="Brakes", summary="Covers braking system requirements"))
    # sibling standards provide MCQ distractors
    db.add(Standard(standard_number="LVVTA_STD_Fuel_Systems", title="Fuel Systems", category="Fuel Systems"))
    db.add(Standard(standard_number="LVVTA_STD_Lighting_Equipment", title="Lighting Equipment", category="Lighting & Electrical"))
    db.commit()
    target = db.query(Standard).filter_by(standard_number="LVVTA_STD_Braking_Systems").first()

    questions = quiz._fallback_quiz_questions(target, db, 5)

    assert len(questions) == 5
    # first question is a category MCQ whose correct answer is in its own options
    q0 = questions[0]
    assert q0.correct_answer == "Brakes"
    assert "Brakes" in q0.options
    # every MCQ's correct answer must be one of its options; text questions have none
    for q in questions:
        if q.options:
            assert q.correct_answer in q.options
    # deterministic: same inputs -> same questions
    again = quiz._fallback_quiz_questions(target, db, 5)
    assert [q.question for q in again] == [q.question for q in questions]
    db.close()


def test_fallback_quiz_handles_lone_standard(TestingSessionLocal):
    db = TestingSessionLocal()
    db.add(Standard(standard_number="ONLY", title="Only Standard", category="Misc", summary="x"))
    db.commit()
    target = db.query(Standard).filter_by(standard_number="ONLY").first()
    # no siblings, no other categories -> still returns at least one usable question
    questions = quiz._fallback_quiz_questions(target, db, 5)
    assert len(questions) >= 1
    assert all(q.question for q in questions)
    db.close()


# --------------------------------------------------------------------------- #
# seed_standards_from_chroma
# --------------------------------------------------------------------------- #
class FakeCorpusCollection:
    """Returns every chunk's metadata on .get(include=[...]) like a real corpus."""

    def __init__(self, metadatas):
        self._metadatas = metadatas

    def get(self, where=None, include=None, limit=None):
        return {"metadatas": self._metadatas}


def test_seed_standards_from_chroma_creates_and_updates(TestingSessionLocal, monkeypatch):
    # a pre-existing row missing pdf_url, and one already complete
    db = TestingSessionLocal()
    db.add(Standard(standard_number="ORS_Chapter_3", title="ORS Ch 3", category="Certification Process", pdf_url=None))
    db.add(Standard(standard_number="HAS_ALL", title="Complete", category="Brakes", pdf_url="https://x/done.pdf"))
    db.commit()
    db.close()

    # two chunks for ORS_Chapter_3 (must collapse to one), a brand-new standard, and HAS_ALL
    corpus = FakeCorpusCollection([
        {"standard_number": "ORS_Chapter_3", "title": "ORS Ch 3", "category": "Certification Process", "pdf_url": "https://x/ors3.pdf"},
        {"standard_number": "ORS_Chapter_3", "title": "ORS Ch 3", "category": "Certification Process", "pdf_url": "https://x/ors3.pdf"},
        {"standard_number": "LVVTA_STD_Frontal_Impact", "title": "Frontal Impact", "category": "General Compliance", "pdf_url": "https://x/frontal.pdf"},
        {"standard_number": "HAS_ALL", "title": "Complete", "category": "Brakes", "pdf_url": "https://x/done.pdf"},
    ])
    monkeypatch.setattr(pdf_indexer, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(pdf_indexer, "get_chroma_client", lambda: object())
    monkeypatch.setattr(pdf_indexer, "get_or_create_collection", lambda client: corpus)

    result = pdf_indexer.seed_standards_from_chroma()

    assert result["created"] == 1   # only LVVTA_STD_Frontal_Impact is new
    assert result["updated"] == 1   # ORS_Chapter_3 gets its pdf_url backfilled

    db = TestingSessionLocal()
    new = db.query(Standard).filter_by(standard_number="LVVTA_STD_Frontal_Impact").first()
    assert new is not None and new.pdf_url == "https://x/frontal.pdf" and new.category == "General Compliance"
    assert db.query(Standard).filter_by(standard_number="ORS_Chapter_3").first().pdf_url == "https://x/ors3.pdf"
    # total rows: ORS_Chapter_3, HAS_ALL, LVVTA_STD_Frontal_Impact = 3 (no duplicate from the 2 chunks)
    assert db.query(Standard).count() == 3
    db.close()
