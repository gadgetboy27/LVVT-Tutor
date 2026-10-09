"""Study guide: quote verification, pipeline, persistence, API."""
import json
import os

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL") or "sqlite://"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import study as study_api
from app.core.database import Base, get_db
from app.models.quiz import Standard
from app.models.study import StudyPoint
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.rag import study_guide as sg

PAGES = [
    "Cover page. Disclaimer and contact details.",
    "2.2(1) A braking system must use purpose-designed auto-\nmotive components that are compatible with each other.",
    "2.2(7) The removal of an Anti-lock Braking System (ABS) must not prevent the braking system from operating "
    "effectively and safely. Five working days is the response timeframe.",
]


# --------------------------------------------------------------------------- verification
def test_quote_is_found_despite_line_breaks_hyphens_and_smart_quotes():
    q = "A braking system must use purpose-designed automotive components that are compatible"
    assert sg.locate_quote(q, PAGES) == 2
    assert sg.locate_quote("The removal of an Anti‑lock Braking System (ABS) must not prevent the braking system", PAGES) == 3


def test_invented_or_too_short_quotes_are_rejected():
    assert sg.locate_quote("A braking system must have dual circuits and a proportioning valve fitted", PAGES) is None
    assert sg.locate_quote("must not", PAGES) is None          # too short to prove anything
    assert sg.locate_quote("", PAGES) is None


def test_claimed_page_is_only_a_hint():
    q = "The removal of an Anti-lock Braking System (ABS) must not prevent the braking system"
    assert sg.locate_quote(q, PAGES, near=1) == 3               # wrong claim, right page returned


def test_windows_group_pages_and_skip_blank_ones():
    w = sg.make_windows(["a" * 4000, "", "b" * 4000, "c" * 100], max_chars=6500)
    assert [[n for n, _ in win] for win in w] == [[1], [3, 4]]


# --------------------------------------------------------------------------- pipeline
def _item(**kw):
    base = {"page": 2, "category": "Requirement", "importance": 1, "point": "Brake parts must be automotive grade.",
            "quote": "A braking system must use purpose-designed automotive components that are compatible",
            "section": "2.2(1)"}
    base.update(kw)
    return base


def test_build_guide_keeps_only_verified_points_and_dedupes(monkeypatch):
    monkeypatch.setattr(sg, "extract_pages", lambda b: PAGES)
    replies = [json.dumps([
        _item(),
        _item(),                                                        # duplicate quote
        _item(quote="A braking system must have dual circuits and a proportioning valve fitted"),   # invented
        _item(page=3, category="Nonsense", importance=9,
              quote="The removal of an Anti-lock Braking System (ABS) must not prevent the braking system",
              point="ABS removal must not make braking unsafe.", section="2.2(7)"),
        _item(point="  "),                                              # empty restatement
    ])]
    g = sg.build_guide(b"%PDF", "Braking", lambda s, u, m: replies.pop(0), workers=1)
    assert g["stats"]["proposed"] == 5 and g["stats"]["verified"] == 2
    assert [p["page"] for p in g["points"]] == [2, 3]
    assert g["points"][1]["category"] == "Requirement" and g["points"][1]["importance"] == 2   # sanitised
    assert g["stats"]["pages_with_points"] == [2, 3]


def test_unparseable_and_failed_windows_are_counted_not_fatal(monkeypatch):
    monkeypatch.setattr(sg, "extract_pages", lambda b: ["x" * 5000, "y" * 5000])
    calls = iter(["not json at all", RuntimeError("api down")])

    def llm(s, u, m):
        r = next(calls)
        if isinstance(r, Exception):
            raise r
        return r
    g = sg.build_guide(b"%PDF", "T", llm, workers=1)
    assert g["points"] == [] and g["stats"]["windows"] == 2 and g["stats"]["failed_windows"] == 1


# --------------------------------------------------------------------------- persistence + API
@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(email="a@b.co", hashed_password="x")
    std = Standard(standard_number="BRK", title="Braking", pdf_url="u", content_hash="a" * 64)
    db.add_all([user, std]); db.commit()
    app = FastAPI()
    app.include_router(study_api.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    study_api._generating.clear(); study_api._failed.clear()
    yield TestClient(app), db, std, Session
    db.close(); engine.dispose()


def _guide(h="a" * 64):
    return {"points": [{"page": 2, "category": "Requirement", "importance": 1, "point": "p", "quote": "q" * 40, "section": "2.2"},
                       {"page": 3, "category": "Limit or figure", "importance": 3, "point": "p2", "quote": "r" * 40, "section": ""}],
            "source_hash": h}


def test_status_progression(env):
    client, db, std, _ = env
    assert client.get("/api/study/BRK").json()["status"] == "missing"
    sg.replace_points(db, std.id, _guide())
    r = client.get("/api/study/BRK").json()
    assert r["status"] == "ready" and r["counts"] == {"1": 1, "3": 1} and r["pages_with_points"] == [2, 3]
    assert r["original_pdf"] == "/api/pdf/view/BRK"
    std.content_hash = "b" * 64; db.commit()                       # the PDF changed since the notes were built
    assert client.get("/api/study/BRK").json()["status"] == "outdated"
    assert client.get("/api/study/NOPE").status_code == 404


def test_generate_runs_once_and_reports_failure(env, monkeypatch):
    client, db, std, Session = env
    monkeypatch.setattr(study_api, "SessionLocal", Session)
    monkeypatch.setattr(study_api, "_ensure_cached_pdf", lambda s: None)
    study_api._generating.add("BRK")
    assert client.post("/api/study/BRK/generate").json() == {"status": "generating"}   # already running: no second build
    study_api._generating.clear()
    study_api._generate("BRK")                                       # PDF unavailable
    assert client.get("/api/study/BRK").json()["status"] == "failed"


def test_generate_stores_points(env, monkeypatch, tmp_path):
    client, db, std, Session = env
    pdf = tmp_path / "x.pdf"; pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(study_api, "SessionLocal", Session)
    monkeypatch.setattr(study_api, "_ensure_cached_pdf", lambda s: str(pdf))
    monkeypatch.setattr(study_api.study_guide, "default_llm", lambda: None)
    monkeypatch.setattr(study_api.study_guide, "build_guide",
                        lambda b, t, llm: {**_guide(), "stats": {"windows": 1, "failed_windows": 0}})
    study_api._generating.add("BRK")
    study_api._generate("BRK")
    assert "BRK" not in study_api._generating
    assert client.get("/api/study/BRK").json()["status"] == "ready"


def test_generate_marks_failed_when_every_ai_call_failed(env, monkeypatch, tmp_path):
    client, db, std, Session = env
    pdf = tmp_path / "x.pdf"; pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(study_api, "SessionLocal", Session)
    monkeypatch.setattr(study_api, "_ensure_cached_pdf", lambda s: str(pdf))
    monkeypatch.setattr(study_api.study_guide, "default_llm", lambda: None)
    monkeypatch.setattr(study_api.study_guide, "build_guide",
                        lambda b, t, llm: {"points": [], "source_hash": "z", "stats": {"windows": 3, "failed_windows": 3}})
    study_api._generate("BRK")
    r = client.get("/api/study/BRK").json()
    assert r["status"] == "failed" and "AI service" in r["error"]


def test_export_and_idempotent_load_roundtrip(env, tmp_path):
    client, db, std, Session = env
    sg.replace_points(db, std.id, _guide())
    path = str(tmp_path / "g.json.gz")
    assert sg.export_points(db, path) == 2
    db.query(StudyPoint).delete(); db.commit()
    assert sg.load_points(db, path) == {"added": 2, "standards": 1}
    assert sg.load_points(db, path) == {"added": 0, "standards": 0}   # standards that already have notes are left alone
    assert "not found" in sg.load_points(db, str(tmp_path / "missing"))["skipped"]


def test_refresh_drops_notes_for_a_changed_pdf(monkeypatch):
    from datetime import datetime
    from app.services.rag import pdf_refresh
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    a = Standard(standard_number="CHANGED", title="c", pdf_url="u1", last_modified=datetime(2026, 1, 1), content_hash="h1")
    b = Standard(standard_number="SAME", title="s", pdf_url="u2", last_modified=datetime(2026, 1, 1), content_hash="h2")
    s.add_all([a, b]); s.commit()
    sg.replace_points(s, a.id, _guide()); sg.replace_points(s, b.id, _guide())
    monkeypatch.setattr(pdf_refresh, "SessionLocal", Session)
    monkeypatch.setattr(pdf_refresh, "remote_last_modified", lambda url: datetime(2026, 9, 1))
    monkeypatch.setattr(pdf_refresh, "index_pdf_to_vectordb",
                        lambda sn, t, u, c, refresh=False, expected_hash=None:
                        {"success": True, "unchanged": True, "content_hash": expected_hash} if sn == "SAME"
                        else {"success": True, "content_hash": "new"})
    pdf_refresh.refresh_stale_pdfs()
    check = Session()
    assert check.query(StudyPoint).filter_by(standard_id=a.id).count() == 0     # rebuilt text -> old notes dropped
    assert check.query(StudyPoint).filter_by(standard_id=b.id).count() == 2     # same bytes -> notes kept
