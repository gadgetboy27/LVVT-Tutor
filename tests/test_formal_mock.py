"""Mock Formal Assessment (20 closed-book MCQs, 30 min, 15 to pass) + grading helpers
+ the PDF freshness refresher."""
import os

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL") or "sqlite://"

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.enhanced import PracticeExam
from app.models.quiz import Standard
from app.models.user import User
from app.api import practice_exam
from app.services.auth.jwt import get_current_user
from app.services.quiz.grading import correct_index, is_answer_correct


# --------------------------------------------------------------------------- grading
OPTS = ["A) Dual circuit", "B) Single circuit", "C) Drum only", "D) None"]


@pytest.mark.parametrize("correct", ["B", "b", "B) Single circuit", "Single circuit"])
def test_correct_answer_formats_resolve_to_same_option(correct):
    q = {"options": OPTS, "correct_answer": correct}
    assert correct_index(q) == 1
    assert is_answer_correct(q, "B") and not is_answer_correct(q, "A")


def test_unresolvable_answer_is_never_correct():
    q = {"options": OPTS, "correct_answer": "Z"}
    assert correct_index(q) == -1 and not is_answer_correct(q, "A")
    assert not is_answer_correct({"options": OPTS, "correct_answer": "A"}, "")


# --------------------------------------------------------------------------- endpoints
@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    db = Session()
    user = User(email="x@y.co", hashed_password="x")
    db.add_all([user, Standard(standard_number="BRK", title="Braking", category="Brakes"),
                Standard(standard_number="FUEL", title="Fuel", category="Fuel")])
    db.commit()

    calls = {"n": 0}

    def fake_gen(context, standard_number, n):
        calls["n"] += 1   # distinct text per call, like a real model would vary
        return [{"question": f"{standard_number} question {calls['n']}-{i}?", "options": list(OPTS),
                 "correct_answer": "A", "explanation": "see doc"} for i in range(n)]

    class FakeCollection: ...
    monkeypatch.setattr(practice_exam, "get_chroma_client", lambda: None)
    monkeypatch.setattr(practice_exam, "get_or_create_collection", lambda c: FakeCollection())
    monkeypatch.setattr(practice_exam, "query_documents", lambda *a, **k: {"documents": [["chunk text"]]})
    monkeypatch.setattr(practice_exam, "generate_quiz_questions", fake_gen)

    app = FastAPI()
    app.include_router(practice_exam.router)

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: db.query(User).first()
    yield TestClient(app), db
    db.close()
    engine.dispose()


def test_formal_start_hides_answers_and_sets_rules(env):
    client, _ = env
    r = client.post("/api/practice-exam/formal/start")
    assert r.status_code == 200
    data = r.json()
    assert data["time_limit_minutes"] == 30 and data["pass_mark_pct"] == 75
    assert data["total_questions"] == 20 and data["required_correct"] == 15
    for q in data["questions"]:
        assert "correct_answer" not in q and "explanation" not in q
        assert q["standard_number"] in ("BRK", "FUEL")
    assert {q["standard_number"] for q in data["questions"]} == {"BRK", "FUEL"}   # spread across standards


def test_formal_start_503_when_no_questions_can_be_generated(env, monkeypatch):
    client, _ = env
    monkeypatch.setattr(practice_exam, "generate_quiz_questions", lambda *a, **k: [])
    assert client.post("/api/practice-exam/formal/start").status_code == 503


def _submit(client, exam, n_correct):
    answers = {str(q["question_id"]): ("A" if i < n_correct else "B")
               for i, q in enumerate(exam["questions"])}
    return client.post("/api/practice-exam/submit", json={"exam_id": exam["id"], "answers": answers}).json()


def test_15_of_20_passes_14_fails(env):
    client, _ = env
    exam = client.post("/api/practice-exam/formal/start").json()
    res = _submit(client, exam, 15)
    assert res["correct_answers"] == 15 and res["required_correct"] == 15 and res["passed"] is True
    assert all("explanation" in r for r in res["results"])        # review data comes back after submit

    exam2 = client.post("/api/practice-exam/formal/start").json()
    res2 = _submit(client, exam2, 14)
    assert res2["passed"] is False


def test_late_submission_fails_even_with_enough_correct(env):
    client, db = env
    exam = client.post("/api/practice-exam/formal/start").json()
    row = db.get(PracticeExam, exam["id"])
    row.started_at = datetime.utcnow() - timedelta(minutes=45)
    db.commit()
    res = _submit(client, exam, 20)
    assert res["timed_out"] is True and res["passed"] is False


def test_exam_history_endpoint_works(env):
    client, _ = env
    client.post("/api/practice-exam/formal/start")
    assert client.get("/api/practice-exam/history/all").status_code == 200


# --------------------------------------------------------------------------- PDF freshness
def test_refresh_only_reindexes_changed_pdfs(monkeypatch):
    from app.services.rag import pdf_refresh

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    seed = Session()
    old = datetime(2026, 1, 15)
    seed.add_all([
        Standard(standard_number="FRESH", title="Fresh", pdf_url="u/fresh", last_modified=old, content_hash="h1"),
        Standard(standard_number="STALE", title="Stale", pdf_url="u/stale", last_modified=old, content_hash="h2"),
        Standard(standard_number="NEVER", title="Never", pdf_url="u/never"),
        Standard(standard_number="SAME", title="Same bytes", pdf_url="u/same", last_modified=old, content_hash="h4"),
        Standard(standard_number="NOURL", title="No url"),
    ])
    seed.commit()
    seed.close()

    remote = {"u/fresh": old, "u/stale": datetime(2026, 8, 17), "u/never": None, "u/same": datetime(2026, 9, 1)}
    indexed = []

    def fake_index(sn, title, url, cat, refresh=False, expected_hash=None):
        indexed.append(sn)
        if sn == "SAME":
            return {"success": True, "unchanged": True, "content_hash": expected_hash}
        return {"success": True, "content_hash": f"new-{sn}"}

    monkeypatch.setattr(pdf_refresh, "SessionLocal", Session)
    monkeypatch.setattr(pdf_refresh, "remote_last_modified", lambda url: remote[url])
    monkeypatch.setattr(pdf_refresh, "index_pdf_to_vectordb", fake_index)

    out = pdf_refresh.refresh_stale_pdfs()
    assert out["checked"] == 4 and out["fresh"] == 1 and out["unchanged"] == 1
    assert sorted(out["reindexed"]) == ["NEVER", "STALE"]
    assert "FRESH" not in indexed and "NOURL" not in indexed

    check = Session()
    assert check.query(Standard).filter_by(standard_number="STALE").one().last_modified == datetime(2026, 8, 17)
    assert check.query(Standard).filter_by(standard_number="STALE").one().content_hash == "new-STALE"
    # second run: everything with a known date is up to date (SAME's date advanced too);
    # NEVER has no remote date, so it is re-checked by hash
    indexed.clear()
    out2 = pdf_refresh.refresh_stale_pdfs()
    assert out2["fresh"] == 3 and indexed == ["NEVER"]
    check.close()
